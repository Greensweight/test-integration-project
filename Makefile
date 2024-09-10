install:
	ansible-galaxy install -r requirements.yml --force

sample: install
	ansible-playbook playbooks/sample-test-case.yml

test-case-1: install
	ansible-playbook playbooks/test-case-1.yml