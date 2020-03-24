FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:latest AS runtime

RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -r requirements.txt
RUN python3 -m pip install -r requirements-dev.txt -r requirements-tst.txt -e .
