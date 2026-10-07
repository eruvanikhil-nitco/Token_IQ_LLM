Additional files for the proxy. Reduces the size of the main litellm package.

Currently, only stores the migration.sql files for litellm-proxy.

To install, run:

```bash
uv add token-iq-migrations
```
OR 

```bash
uv tool install 'litellm[proxy]' # installs token-iq-migrations and other proxy dependencies
```

To use the migrations, run:

```bash
litellm --use_prisma_migrate
```
