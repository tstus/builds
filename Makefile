lint : pkg_list = $(shell find host-os-build.py setup_environment.py upgrade_versions.py lib tools extras -name "*.py")

all: clean config
	python host-os-build.py --build-version add-$(pkg) --package $(pkg)
lint:
	pylint -E  $(pkg_list) || :
	@echo
	pycodestyle $(pkg_list) || :
config:
	sed -i s"!\(log_file\).*!\1: '/home/user/builds/logs/builds.log'!" config.yaml
	sed -i s"!\(repositories_path\).*!\1: '/home/user/builds/repositories'!" config.yaml
	sed -i s"!\(build_versions_repository_url\):.*!\1: 'file:///home/user/versions'!" config.yaml
	echo " verbose: true" >> config.yaml
prereq:
	yum install --downloadonly --downloaddir=. epel-release
	yum localinstall epel-release-*.rpm
	yum install -y bzip2 git mock python-pygit2 PyYAML svn wget
clean:
	rm -rf components
	rm -rf build
	rm -rf logs
	git checkout config.yaml
	rm -f epel-release*
tmpclean:
	find . -name "*~" -delete
distclean: clean
	rm -rf repositories
	rm -rf result
.PHONY: clean distclean tmpclean lint config prereq
