SHELL:=/bin/bash


help: ### Display this help screen
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
.PHONY: help

docker: ### Build and tag docker image
	docker build --tag aiograpi:future .
.PHONY: docker

sync: ### Sync fork with upstream repo
	git remote add upstream 'https://github.com/subzeroid/aiograpi' || true;
	git fetch upstream;
	git merge upstream/main;
.PHONY: sync