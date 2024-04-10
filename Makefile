install:
	vf activate order
	pip3 install -r requirements.txt

upgrade:
	vf activate order
	sudo echo Upgrading Order Master
	git pull
	pip3 install -r requirements.txt
	tools/purge_cache.fish
	tools/upgrade_db.fish
	sudo systemctl reload order.*
	sudo supervisorctl restart all

analyze:
	coverage run -m pytest tests
	coverage xml
	/Users/ralfeus/temp/sonar-scanner-5.0.1.3006-macosx/bin/sonar-scanner
	rm coverage.xml