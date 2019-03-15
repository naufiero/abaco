import json

from models import ExecutionsSummary, AbacoDAO, CacheExecutionsSummary

from stores import actors_store, stats_store, executions_store





def main():
    ids = get_actor_ids()
    tc = CacheExecutionsSummary.get_empty_cache()
    for dbid in ids:
        actorcache = UpdateCacheActorStats(dbid, tc)
        actorcache.update_stats_store()
    # am i updating correctly
    stats_store.update['summary'] = tc




def get_actor_ids():
    """Returns the list of actor ids currently registered."""
    return [db_id for db_id, _ in actors_store.items()]


class UpdateCacheActorStats:

    def __init__(self, db_id, tc):
        self.db_id = db_id
        self.es = ExecutionsSummary(db_id)
        self.tc = tc

    def update_stats_store(self, db_id):
        stats_store[db_id] = {'actor_id': self.es.actor_id,
                              'api_server': self.es.api_server,
                              'owner': self.es.owner,
                              'executions': self.es.executions,
                              'total_executions': self.es.total_executions,
                              'total_io': self.es.total_io,
                              'total_runtime': self.es.total_runtime,
                              'total_cpu': self.es.total_cpu}

        for actor_dbid, executions in executions_store.items():

            actor_exs = 0
            actor_runtime = 0
            actor_io = 0
            actor_cpu = 0
            for ex_id, execution in executions.items():
                actor_exs += 1
                actor_runtime += execution.get('runtime', 0)
                actor_io += execution.get('io', 0)
                actor_cpu += execution.get('cpu', 0)

            self.tc['summary']['total_actors_all'] += 1
            self.tc['summary']['total_executions_all'] += actor_exs
            self.tc['summary']['total_execution_runtime_all'] += actor_runtime
            self.tc['summary']['total_execution_io_all'] += actor_io
            self.tc['summary']['total_execution_cpu_all'] += actor_cpu
            self.tc['summary']['total_actors_existing'] += 1
            self.tc['summary']['total_executions_existing'] += actor_exs
            self.tc['summary']['total_execution_runtime_existing'] += actor_runtime
            self.tc['summary']['total_execution_io_existing'] += actor_io
            self.tc['summary']['total_execution_cpu_existing'] += actor_cpu







# main engine loop that gets all of the actor ids
# each loop will instiatie a class object with the actor id, then update the actor id
# db_id = <trnant>_<actor_id>
# stats_store[db_id] = {dictionary }


if __name__ == '__main__':
    main()