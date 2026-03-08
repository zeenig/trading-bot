from app.execution.engine import get_engine


def run_once():
    return get_engine().run_cycle()
