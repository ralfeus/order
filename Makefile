install:
	vf activate order
	pip3 install -r requirements.txt

upgrade:
	vf activate order
	sudo echo Upgrading Order Master
	git pull
	pip3 install -r requirements.txt
	tools/clear-cloudflare-cache.fish
	#tools/clear-flask-cache.fish
	tools/upgrade_db.fish
	sudo systemctl reload order.*
	sudo supervisorctl restart all

analyze:
	coverage run -m pytest tests
	coverage xml
	/Users/ralfeus/temp/sonar-scanner-5.0.1.3006-macosx/bin/sonar-scanner
	rm coverage.xml

network-manager-docker:
	cat ~/.docker/ralfeus.pass | docker login -u ralfeus --password-stdin
	docker buildx build --push --platform linux/arm64,linux/amd64 -t ralfeus/network-manager:stable . -f network_builder/Dockerfile