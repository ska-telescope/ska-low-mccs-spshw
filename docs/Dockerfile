FROM readthedocs/build:latest

ARG dir=docs
ENV dir=${dir}

COPY ${dir}/requirements.txt .
RUN python3 -m venv /home/docs/my_env && /home/docs/my_env/bin/pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# TODO: Restore -n ("nitpicky") flag once we catch up to ska_tango_base 0.11.0
# ENTRYPOINT /home/docs/my_env/bin/sphinx-build -T -E -b html -n -W --keep-going project/${dir}/source project/${dir}/build/html
ENTRYPOINT /home/docs/my_env/bin/sphinx-build -T -E -b html -W --keep-going project/${dir}/source project/${dir}/build/html
