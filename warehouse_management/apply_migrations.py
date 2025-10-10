# Example of how to apply migrations in TEEHR
import teehr

ev = teehr.Evaluation(
    local_warehouse_dir="warehouse_template",
    create_local_dir=False,
    check_evaluation_version=False
)

# Switch to the remote catalog.
ev.set_active_catalog("remote")

# Apply any pending migrations. This will check to see if a "migrations"
# directory exists in the warehouse dir and apply any new migration
# scripts found there.
ev.apply_migrations()
