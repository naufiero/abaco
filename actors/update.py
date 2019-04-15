import json


from models import ExecutionsSummary, Actor, CacheExecutionsSummary

from stores import actors_store, stats_store, executions_store


from pymongo import MongoClient



def main():
    ids = get_actor_ids()
    print(ids)

    # creates empty summary dict
    ces = CacheExecutionsSummary()
    tc = ces.get_empty_cache()

    # gets list of actor ids from actors_store
    for dbid in ids:
        decoded_dbid = dbid.decode("utf-8")
        actorcache = UpdateCacheActorStats(decoded_dbid, tc)
        # updates each actor in stats store
        actorcache.update_stats_store()
        # counts the actors in the actor_store
        tc['summary']['total_actors_existing'] += 1

    # gets and deletes all actors in stats_store but not in actors_store, including summary
    get_delete_list()

    # updates the summary
    actorcache.update_summary()
    # for key, value in stats_store.items():
    #     print(key, value)

# Returns the list of actor ids currently in actors_store
def get_actor_ids():
    return [db_id for db_id, _ in actors_store.items()]


# iterates through a list of ids and deletes them from the stats_store
def delete_actor_from_stats_store(delete_list):
    print(delete_list)

    for id in delete_list:
        print(id)
        stats_store.__delitem__(id)

    actors_from_stats_store_test = [db_id for db_id, _ in stats_store.items()]
    print(actors_from_stats_store_test)


# gets a list of actors that need to be deleted from stats_store
def get_delete_list():

    # get list of current actor_store actors
    encoded_ids = [db_id for db_id, _ in actors_store.items()]
    actors_from_actor_store = []
    for id in encoded_ids:
        decoded_dbid = id.decode("utf-8")
        actors_from_actor_store.append(decoded_dbid)

    # get list of current stats_store actors
    actors_from_stats_store = [db_id for db_id, _ in stats_store.items()]

    # generate list of stats_store actors that should be deleted
    delete_list = list(set(actors_from_stats_store) - set(actors_from_actor_store))

    # call method to delete these actors from stats_store
    delete_actor_from_stats_store(delete_list)


# when initalized, creates an instance of ExecutionsSummary from the views.
# this class is what causes timeout issues; updates executions for that actor
class UpdateCacheActorStats:

    def __init__(self, db_id, tc):
        self.db_id = db_id
        self.tc = tc
        self.es = ExecutionsSummary(db_id=db_id)


    # update stats_store per actor id
    def update_stats_store(self):

        stats_store[self.db_id] = {'actor_id': self.es.actor_id,
                              'api_server': self.es.api_server,
                              'owner': self.es.owner,
                              'executions': self.es.executions,
                              'total_executions': self.es.total_executions,
                              'total_io': self.es.total_io,
                              'total_runtime': self.es.total_runtime,
                              'total_cpu': self.es.total_cpu}


    def update_summary(self):
        for actor_dbid, executions in executions_store.items():
            actor = None
            try:
                actor = Actor.from_db(actors_store[self.db_id])
            except KeyError:
                pass

            actor_exs = 0
            actor_runtime = 0
            actor_io = 0
            actor_cpu = 0

            # get all execution ids for this actor
            for ex_id, execution in executions.items():
                actor_exs += 1
                actor_runtime += execution.get('runtime', 0)
                actor_io += execution.get('io', 0)
                actor_cpu += execution.get('cpu', 0)


            self.tc['summary']['total_executions_all'] += actor_exs
            self.tc['summary']['total_execution_runtime_all'] += actor_runtime
            self.tc['summary']['total_execution_io_all'] += actor_io
            self.tc['summary']['total_execution_cpu_all'] += actor_cpu
            if actor:
                self.tc['summary']['total_actors_all'] += 1
                self.tc['summary']['total_executions_existing'] += actor_exs
                self.tc['summary']['total_execution_runtime_existing'] += actor_runtime
                self.tc['summary']['total_execution_io_existing'] += actor_io
                self.tc['summary']['total_execution_cpu_existing'] += actor_cpu



        stats_store['summary'] = self.tc['summary']











# main engine loop that gets all of the actor ids
# each loop will instiatie a class object with the actor id, then update the actor id
# db_id = <trnant>_<actor_id>
# stats_store[db_id] = {dictionary }


if __name__ == '__main__':
    main()