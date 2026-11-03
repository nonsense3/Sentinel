# Sentinel task runner (Unix/macOS). Windows users: use .\make.ps1 <target>.
.PHONY: up down deploy demo test samples logs alerts dlq dashboard clean reset

up: ## Start LocalStack and deploy everything
	docker compose up -d --wait
	$(MAKE) deploy

deploy: ## terraform init + apply
	cd terraform && terraform init -input=false && terraform apply -auto-approve

demo: samples ## Upload sample files and print the verdict table
	python scripts/demo.py

samples: ## Generate harmless sample files
	python scripts/make_samples.py

test: ## Run unit tests
	python -m pytest -q

logs: ## Tail LocalStack logs
	docker compose logs -f localstack

alerts: ## Show SECURITY ALERT lines from the alerts Lambda
	docker compose logs localstack | grep "SECURITY ALERT" || echo "no alerts yet"

dlq: ## Show approximate DLQ depth
	awslocal sqs get-queue-attributes \
	  --queue-url $$(cd terraform && terraform output -raw scan_dlq_url) \
	  --attribute-names ApproximateNumberOfMessages

dashboard: ## Serve the visual dashboard at http://localhost:8080
	python dashboard/server.py

down: ## Stop LocalStack
	docker compose down

reset: ## Tear down everything including volumes and terraform state
	docker compose down -v
	rm -rf terraform/.terraform terraform/terraform.tfstate* terraform/build samples
