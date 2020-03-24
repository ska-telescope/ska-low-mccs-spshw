
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:latest AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create
# ENV TANGO_HOST=test-databaseds:10000
RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -r requirements.txt
RUN python3 -m pip install .

