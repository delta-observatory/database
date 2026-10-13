FROM postgres:18-alpine
COPY migrations/ /migrations/
COPY migrate.sh /usr/local/bin/migrate
ENV MIGRATIONS_DIR=/migrations
USER postgres
ENTRYPOINT ["/usr/local/bin/migrate"]
