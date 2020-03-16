import xml.etree.cElementTree as ET
from string import Template

import requests


class Repository:

    def get_latest_release(self, repo):
        headers = {
            'User-Agent': 'pyscript',
            'Content-Type': 'application/json',
            'Authorization': "token %s" % self.token,
        }
        url = f"https://api.github.com/repos/{repo}/releases/latest"

        print(url)

        return requests.get(url, headers=headers)

    def get_asset_for_ij(self, assets, ij):
        return next((url for url in assets if ij in url), assets)

    def get_asset_urls(self, release, plugin_repo):
        release_version = release['tag_name']

        (stable, nightly) = release_version.split('.')

        asset_urls = [asset['browser_download_url'] for asset in release['assets']]

        version_template = Template(self.plugin_repos[plugin_repo]['version_tpl'])

        assets = {
            'stable': [
                {
                    'version': version,
                    'url': self.get_asset_for_ij(asset_urls, version).replace(release_version, stable + ".0"),
                    'plugin-version': version_template.substitute({'version': version, 'tag': stable + ".0"}),
                    **self.plugin_repos[plugin_repo],
                }
                for version in self.plugin_repos[plugin_repo]['versions']
            ],
            'nightly': [
                {
                    'version': version,
                    'url': self.get_asset_for_ij(asset_urls, version),
                    'plugin-version': version_template.substitute({'version': version, 'tag': release_version}),
                    **self.plugin_repos[plugin_repo],
                }
                for version in self.plugin_repos[plugin_repo]['versions']

            ],
        }

        return assets

    def __init__(self, plugin_repos, token):
        self.token = token
        self.plugin_repos = plugin_repos

    def generate_repo_xmls(self, channel_urls):
        root = ET.Element('plugin-repository')
        category = ET.SubElement(root, 'Category', {'name': 'Build'})
        for info in channel_urls:
            for version in info:
                plugin = ET.SubElement(category, 'idea-plugin')
                ET.SubElement(plugin, 'id').text = version['id']
                ET.SubElement(
                    plugin,
                    'idea-version',
                    {
                        'since-build': version['version'] + '.0',
                        'until-build': version['version'] + '.*'
                    }
                )
                ET.SubElement(plugin, 'name').text = version['name']
                ET.SubElement(plugin, 'version').text = version['plugin-version']
                ET.SubElement(plugin, 'download-url').text = version['url']

        return ET.tostring(root)

    def latest_repo(self):
        all_urls_by_channel = {
            'stable': [],
            'nightly': [],
        }

        for plugin_repo in self.plugin_repos:
            release = self.get_latest_release(plugin_repo).json()
            urls = self.get_asset_urls(release, plugin_repo)

            for channel in urls:
                all_urls_by_channel[channel].append(urls[channel])

        for channel in all_urls_by_channel:
            xml = self.generate_repo_xmls(all_urls_by_channel[channel])
            open('docs/' + channel + '.xml', 'wb').write(xml)
