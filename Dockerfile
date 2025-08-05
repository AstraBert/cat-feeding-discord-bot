FROM ghcr.io/astral-sh/uv:python3.13-alpine

WORKDIR /bot/

COPY ./ /bot/

RUN uv sync

ENTRYPOINT [ "uv", "run", "main.py" ]
