# Copyright (C) IBM Corp. 2016.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import os

from lib import exception
from lib import utils
from lib import distro_utils
from lib import packages_groups_xml_creator
from lib.constants import LATEST_DIR

LOG = logging.getLogger(__name__)


class MockPungiSpinner(object):

    def __init__(self, config):
        self.work_dir = config.get('default').get('work_dir')
        self.timestamp = datetime.datetime.now().isoformat()
        self.result_dir = os.path.join(config.get('default').get('result_dir'),
                                       'iso', self.timestamp)
        self.config = config.get("iso")
        self.distro = self.config.get("iso_name")
        self.version = datetime.date.today().strftime("%y%m%d")
        (_, _, self.arch) = distro_utils.detect_distribution()
        self.mock_binary = config.get('default').get('mock_binary')
        self.mock_args = config.get('default').get('mock_args')

    def _run_mock_command(self, cmd):
        try:
            utils.run_command("%s -r %s %s %s" % (
                self.mock_binary, self.config.get('mock_config'),
                self.mock_args, cmd))
        except exception.SubprocessError:
            LOG.error("Failed to spin ISO")
            raise

    def build(self):
        LOG.info("Starting ISO spin process")
        self._setup()
        self._spin()
        self._save()

    def _setup(self):
        LOG.info("Initializing a chroot")
        self._run_mock_command("--init")

        package_list = ["createrepo", "pungi"]
        LOG.info("Installing %s inside the chroot" % " ".join(package_list))
        self._run_mock_command("--install %s" % " ".join(package_list))

        self._create_spin_repo()

        self._create_spin_kickstart()

    def _create_spin_repo(self):
        LOG.info("Creating spin repository inside chroot")

        LOG.debug("Creating spin repo directory")
        mock_spin_repo_dir = self.config.get('mock_spin_repo').get('dir')
        self._run_mock_command("--shell 'mkdir -p %s'" % mock_spin_repo_dir)

        LOG.debug("Copying rpm to spin repo directory")
        packages_dir = self.config.get('packages_dir')
        rpm_files = utils.recursive_glob(packages_dir, "*.rpm")
        self._run_mock_command("--copyin %s %s" %
                               (" ".join(rpm_files), mock_spin_repo_dir))

        LOG.debug("Creating comps.xml")
        comps_xml_str = packages_groups_xml_creator.create_comps_xml(
            self.config.get('hostos_packages_groups'))
        comps_xml_file = "host-os-comps.xml"
        comps_xml_path = os.path.join(self.work_dir, comps_xml_file)
        try:
            with open(comps_xml_path, 'wt') as f:
                f.write(comps_xml_str)
        except IOError:
            LOG.error("Failed to write XML to %s file." % comps_xml_path)
            raise

        comps_xml_chroot_path = os.path.join("/", comps_xml_file)
        self._run_mock_command("--copyin %s %s" %
                               (comps_xml_path, comps_xml_chroot_path))

        LOG.debug("Creating spin repo")
        createrepo_cmd = "createrepo -v -g %s %s" % (comps_xml_chroot_path,
                                                     mock_spin_repo_dir)
        self._run_mock_command("--shell '%s'" % createrepo_cmd)

    def _create_spin_kickstart(self):
        kickstart_file = self.config.get('kickstart_file')
        kickstart_path = os.path.join(self.work_dir, kickstart_file)
        LOG.info("Creating spin kickstart file %s" % kickstart_path)

        with open(kickstart_path, "wt") as f:
            repo_urls = self.config.get('distro_repo_url')
            mock_spin_repo_name = self.config.get('mock_spin_repo').get('name')
            mock_spin_repo_dir = self.config.get('mock_spin_repo').get('dir')
            repo_urls[mock_spin_repo_name] = "file://%s/" % mock_spin_repo_dir
            for name, url in repo_urls.items():
                repo = ("repo --name=%s --baseurl=%s\n" % (name, url))
                f.write(repo)

            f.write("%packages\n")
            package_group_list = self.config.get('package_group_list')
            for group in self.config.get('hostos_packages_groups').keys():
                group = "@%s" % group
                if group not in package_group_list:
                    package_group_list.append(group)
            for package_group in package_group_list:
                f.write(package_group + "\n")

            f.write("%end\n")

        self._run_mock_command("--copyin %s /" % kickstart_path)

    def _spin(self):
        LOG.info("Spinning ISO")
        spin_cmd = ("pungi -c %s --nosource --nodebuginfo --name %s --ver %s" %
                    (self.config.get('kickstart_file'),
                     self.distro, self.version))
        self._run_mock_command("--shell '%s'" % spin_cmd)

    def _save(self):
        utils.create_directory(self.result_dir)
        latest_dir = os.path.join(os.path.dirname(self.result_dir), LATEST_DIR)
        utils.force_symlink(self.timestamp, latest_dir)

        iso_file = "%s-DVD-%s-%s.iso" % (self.distro, self.arch, self.version)
        checksum_file = ("%s-%s-%s-CHECKSUM" %
                         (self.distro, self.version, self.arch))
        iso_dir = "/%s/%s/iso" % (self.version, self.arch)
        iso_path = os.path.join(iso_dir, iso_file)
        checksum_path = os.path.join(iso_dir, checksum_file)
        chroot_files = "%s %s" % (iso_path, checksum_path)

        LOG.info("Saving ISO %s and checksum %s at %s" %
                 (iso_file, checksum_file, self.result_dir))
        self._run_mock_command("--copyout %s %s" %
                               (chroot_files, self.result_dir))

    def clean(self):
        self._run_mock_command("--clean")
