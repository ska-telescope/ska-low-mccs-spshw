FROM readthedocs/build:latest

ARG dir=docs
ENV dir=${dir}

COPY ${dir}/requirements.txt .
RUN python3 -m venv /home/docs/my_env && /home/docs/my_env/bin/pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

ARG UID
ARG GID

ENV GROUP_ID=${GID:-0}
ENV USER_ID=${UID:-0}

ENV USER=${UID:+user}
ENV USER=${USER:-root}

USER root
RUN if [ "$USER" != "root" ] ; then \
    addgroup --gid ${GROUP_ID} ${USER} ; \
    adduser --disabled-password --gecos '' --uid ${USER_ID} --gid ${GROUP_ID} ${USER} ; \
    fi
USER ${USER}

ENTRYPOINT /home/docs/my_env/bin/sphinx-build -T -E -b html -n -W --keep-going project/${dir}/source project/${dir}/build/html
