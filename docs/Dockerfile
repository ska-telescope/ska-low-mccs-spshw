FROM readthedocs/build:latest
ARG dir=docs
ENV dir=${dir}

COPY ${dir}/requirements.txt .
RUN python3 -m pip install --exists-action=w --no-cache-dir --disable-pip-version-check -r requirements.txt

ENTRYPOINT python3 -m sphinx -T -E -b html -n -W --keep-going project/${dir}/source project/${dir}/build/html
