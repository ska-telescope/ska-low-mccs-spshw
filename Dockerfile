FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:9.3.3.1 AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:9.3.3.1 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create
ENV PATH=/home/tango/.local/bin:$PATH
RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -rrequirements.txt -rrequirements-tst.txt .
#CMD ["MccsController", "01"]
