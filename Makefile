install:
	pip3 install -r requirements.txt

upgrade:
	git pull
	tools/purge_cache.fish
	sudo systemctl restart order.*
	sudo supervisorctl restart all