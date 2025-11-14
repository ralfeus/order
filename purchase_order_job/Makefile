default:
	echo qogviv-Rernu5-cinmen | docker login --username ralfeus --password-stdin
	docker buildx build --platform linux/amd64,linux/arm64/v8 -t ralfeus/purchase-order-job:latest --push .