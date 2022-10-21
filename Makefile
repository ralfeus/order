install:
	pip3 install -r requirements.txt

upgrade:
	git pull
	sudo systemctl restart order.*