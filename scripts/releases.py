from string import Template

import requests


class Releases:
    base = 'https://api.github.com'

    def __init__(self, token, owner, repo, ij_versions, artifactory_url_tpl, asset_version_tpl):
        self.asset_version_tpl = asset_version_tpl
        self.artifactory_url_tpl = artifactory_url_tpl
        self.ij_versions = ij_versions
        self.repo = repo
        self.owner = owner
        self.token = token

    def sync_releases(self):
        tags = self.get_tags()
        releases = self.create_missing_releases(tags, self.get_releases())
        self.sync_release_files(releases)

    def delete_releases(self):
        releases = self.get_releases()
        for release in releases:
            for asset in release['assets']:
                requests.delete(asset['url'], headers=self._headers())

    def repo_params(self, other_params=None):
        params = {
            'owner': self.owner,
            'repo': self.repo,
        }
        if other_params is not None:
            params.update(other_params)

        return params

    def _api_url(self, path, params=None):
        template = Template(self.base + path)
        return template.substitute(self.repo_params(params))

    def _headers(self, content_type='application/json'):
        return {
            'User-Agent': 'pyscript',
            'Content-Type': content_type,
            'Authorization': "token %s" % self.token,
        }

    def _release_number(self, tag):
        name = self._tag_name(tag)
        try:
            return float(name)
        except:
            return None

    def get_tags(self, limit=10):
        url = self._api_url("/repos/$owner/$repo/git/refs/tags")
        response = requests.get(url, headers=self._headers())

        # sort and filter
        version_tags = filter(self._release_number, response.json())
        tags = sorted(version_tags, key=self._release_number, reverse=True)

        return tags[:limit]

    def _tag_name(self, tag):
        return tag['ref'].split('/')[2]

    def get_releases(self):
        url = self._api_url("/repos/$owner/$repo/releases")
        return requests.get(url, headers=self._headers()).json()

    def has_release(self, tag, releases):
        for release in releases:
            if release['tag_name'] == self._tag_name(tag):
                return True

        return False

    def create_missing_releases(self, tags, rels):
        for tag in tags:
            if not self.has_release(tag, rels):
                rels.append(self.create_release(tag))

        return rels

    def create_release(self, tag):
        print('creating release for tag ' + tag['ref'])
        url = self._api_url('/repos/$owner/$repo/releases')

        name = self._tag_name(tag)
        body = {
            "tag_name": name,
            "name": name,
        }

        response = requests.post(url, headers=self._headers(), json=body)

        print(response)
        return response.json()

    def has_asset_for_intellij(self, ij_version, rel):
        asset_name = self._asset_version_for(ij_version, rel['tag_name']) + '.zip'
        return asset_name in map(lambda asset: asset['name'], rel['assets'])

    def adjust_version_for_url(self, tag_version):
        stable, nightly = tag_version.split(sep='.')
        if int(stable) <= 12 and int(nightly) == 0:
            return stable
        else:
            return tag_version

    def _asset_version_for(self, ij, tag):
        return Template(self.asset_version_tpl).substitute({
            'version': ij,
            'tag': tag,
        })

    def _artifactory_url(self, asset_version):
        return Template(self.artifactory_url_tpl).substitute({'tpl_version': asset_version})

    def sync_artifactory_to_release(self, version, rel):
        tag = rel['tag_name']
        asset_version = self._asset_version_for(version, tag)
        # new releases will have numbers with .0
        tpl_version = self._asset_version_for(version, self.adjust_version_for_url(tag))
        artifactory_url = self._artifactory_url(tpl_version)
        response = requests.get(artifactory_url)

        if response.status_code != requests.codes.ok:
            print(f"Unsuccessful download of artifact at {artifactory_url} with code {response.status_code}")
            return

        asset_url = (rel['assets_url'] + '?name=' + asset_version + ".zip").replace('api', 'uploads')

        resp = requests.post(
            asset_url,
            headers=self._headers(content_type='application/zip'),
            data=response.content
        )

        print(resp.json()['browser_download_url'])

    def sync_release_files(self, rels):
        for rel in rels:
            for ij in self.ij_versions:
                if not self.has_asset_for_intellij(ij, rel):
                    self.sync_artifactory_to_release(ij, rel)
