FROM nginx:1.27-alpine

COPY index.html /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Syntax-gate the shipped config at build time (this image's "test").
# nginx -t resolves static proxy_pass upstreams at parse time, but
# facts/counter/image only exist at runtime — and BuildKit mounts
# /etc/hosts read-only during RUN. So test a copy of the real config
# with upstream hostnames rewritten to 127.0.0.1 (resolution is all
# nginx -t needs; no connection is made). The shipped config is
# untouched, and the temp files never leave this layer's check.
RUN sed -E 's#(proxy_pass https?://)([a-z]+):([0-9]+)#\1127.0.0.1:\3#' \
      /etc/nginx/conf.d/default.conf > /tmp/default.conf \
 && printf 'events {}\nhttp { include /tmp/default.conf; }\n' > /tmp/nginx-test.conf \
 && nginx -t -c /tmp/nginx-test.conf \
 && rm -f /tmp/default.conf /tmp/nginx-test.conf

EXPOSE 80
