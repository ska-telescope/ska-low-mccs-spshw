FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.16 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.14 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create
ENV PATH=/home/tango/.local/bin:$PATH
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --extra-index-url https://artefact.skao.int/repository/pypi-internal/simple -rrequirements.txt -rtesting/requirements.txt
RUN python3 -m pip install pyfabil-1.0-py3-none-any.whl
RUN python3 -m pip install aavs_system-1.0-py3-none-any.whl
RUN python3 -m pip install .
#CMD ["MccsController", "01"]
