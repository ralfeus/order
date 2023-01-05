install:
	pip3 install -r requirements.txt

upgrade:
	sudo echo Upgrading Order Master
	git pull
	pip3 install -r requirements.txt
	tools/purge_cache.fish
	tools/upgrade_db.fish
	sudo systemctl restart order.*
	sudo supervisorctl restart all