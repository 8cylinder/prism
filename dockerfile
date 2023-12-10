
# docker build -t prism .
# docker run -it prism bash
# docker run -it --mount type=bind,source="$(pwd)",target=/home/sm/app prism bash
## pre-commit install && hatch env create && hatch shell

FROM python:3.10-slim

ARG USER=sm

RUN set -eux; \
    apt update; \
    apt install --yes sudo pipx joe git; \
    useradd --create-home $USER --password "$(openssl passwd -1 password)"; \
    usermod -aG sudo $USER

USER $USER

WORKDIR /home/$USER/prism

# RUN pip install --no-cache-dir --upgrade -r requirements.txt

RUN set -eux; \
    PATH=$HOME/.local/bin:$PATH; \
    echo 'PS1="\n\[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\[\e[35m\][\u]\[\e[m\]\[\033[00m\] \[\033[01;34m\]\w\[\033[00m\]\n\$ "' >> $HOME/.bashrc; \
    echo 'PATH=$HOME/.local/bin:$PATH' >> $HOME/.bashrc; \
    echo 'alias ll="ls -lhAF --color=always"' >> $HOME/.bashrc; \
    echo 'alias ls="ls -A"' >> $HOME/.bashrc; \
    pipx install poetry; \
    pwd; \
    ls -lAh; \
    poetry completions bash >> ~/.bash_completion;

# poetry install;
