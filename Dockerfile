
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:latest AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create
ENV PATH=/home/tango/.local/bin:$PATH
RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -rrequirements.txt .
#CMD ["MccsMaster", "01"]
