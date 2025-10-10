# Example of how to apply migrations in TEEHR
import teehr

ev = teehr.Evaluation(dir_path="evaluation")

ev.set_active_catalog("remote")   

ev.apply_migrations()