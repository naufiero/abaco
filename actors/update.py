import json


from models import ExecutionsSummary, Actor, CacheExecutionsSummary

from stores import actors_store, stats_store, executions_store


from pymongo import MongoClient

try:
    actors_list = stats_store['actors_list']
except KeyError:
    actors_list = []

# summary =  CacheExecutionsSummary()

def main():
    actor_ids = get_actor_ids()
   # print(ids)

    # creates empty summary dict
    ces = CacheExecutionsSummary()
    tc = ces.get_empty_cache()

    decoded_ids = []
    for dbid in actor_ids:
        decoded_dbid = dbid.decode("utf-8")
        decoded_ids.append(decoded_dbid)


    # try execpt and catch keyError
    try:
        if stats_store['summary']:
            actors_from_stats_store = [db_id for db_id, _ in stats_store.items()]
            new_actor_list = list(set(decoded_ids) - set(actors_from_stats_store))
            print(new_actor_list)


            # if stat_store[dbid] does not exist in stats_store:
            for id in new_actor_list:
                actorcache = UpdateCacheActorStats(id)
                # updates each actor in stats store
                actorcache.update_stats_store()
                update_summary(id)
                # counts the actors in the actor_store
                # for key, value in stats_store.items():
                #     print(key, value)
                stats_store['summary']['total_actors_existing'] += 1
                # try: actor not in actor list (it shouldn't be)
                actors_list.append(actorcache.es)
    except KeyError:
        tc = create_summary(tc, actor_ids)
        stats_store['summary'] = tc['summary']
        for id in decoded_ids:

        # if stat_store[dbid] does not exist in stats_store:

            actorcache = UpdateCacheActorStats(id)
            # updates each actor in stats store
            actorcache.update_stats_store()
            # counts the actors in the actor_store
            # for key, value in stats_store.items():
            #     print(key, value)
            # stats_store['summary']['total_actors_existing'] += 1
            # try: actor not in actor list (it shouldn't be)
            actors_list.append(actorcache.es)


# for actors in new_actor list, update summary
# deal with deleted actors here

    # gets and deletes all actors in stats_store but not in actors_store, including summary
    get_delete_list(tc)

    stats_store['actors_list'] = actors_list
    # stats_store['summary'] = summary


    # for key, value in stats_store.items():
    #     print(key, value)
    #     print("______")

# Returns the list of actor ids currently in actors_store
def get_actor_ids():
    return [db_id for db_id, _ in actors_store.items()]


# iterates through a list of ids and deletes them from the stats_store
def delete_actor_from_stats_store(delete_list, tc):
    print(delete_list)

    for del_id in delete_list:
        if del_id != "summary" and del_id != "actors_list":
            print(del_id)
            del stats_store[del_id]
            delete_from_summary(del_id)
    actors_from_stats_store_test = [db_id for db_id, _ in stats_store.items()]
    print(actors_from_stats_store_test)

# gets a list of actors that need to be deleted from stats_store
def get_delete_list(tc):

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
    delete_actor_from_stats_store(delete_list, tc)

# when initalized, creates an instance of ExecutionsSummary from the views.
# this class is what causes timeout issues; updates executions for that actor
class UpdateCacheActorStats:

    def __init__(self, db_id):
        self.db_id = db_id
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

def create_summary(tc, actor_ids):

    for id in actor_ids:

        tc['summary']['total_actors_existing'] += 1
        for actor_dbid, executions in executions_store.items():
            try:
                actor = Actor.from_db(actors_store[id])
            except KeyError:
                actor = None


            actor_exs = 0
            actor_runtime = 0
            actor_io = 0
            actor_cpu = 0


            # executions = executions_store[db_id]
            # get all execution ids for this actor
            for ex_id, execution in executions.items():
                actor_exs += 1
                actor_runtime += execution.get('runtime', 0)
                actor_io += execution.get('io', 0)
                actor_cpu += execution.get('cpu', 0)


            tc['summary']['total_executions_all'] += actor_exs
            tc['summary']['total_execution_runtime_all'] += actor_runtime
            tc['summary']['total_execution_io_all'] += actor_io
            tc['summary']['total_execution_cpu_all'] += actor_cpu
            if actor:
                tc['summary']['total_actors_all'] += 1
                tc['summary']['total_executions_existing'] += actor_exs
                tc['summary']['total_execution_runtime_existing'] += actor_runtime
                tc['summary']['total_execution_io_existing'] += actor_io
                tc['summary']['total_execution_cpu_existing'] += actor_cpu

    return tc



def update_summary(db_id):

    stats_store['summary']['total_actors_existing'] += 1
    # for actor_dbid, executions in executions_store.items():
    try:
        actor = Actor.from_db(actors_store[db_id])
    except KeyError:
        actor = None

    actor_exs = 0
    actor_runtime = 0
    actor_io = 0
    actor_cpu = 0

    print(db_id)
    actor_id = db_id.split('_')[1]
    executions = executions_store[actor_id]
    # get all execution ids for this actor
    for ex_id, execution in executions.items():
        print(ex_id)

        actor_exs += 1
        actor_runtime += execution.get('runtime', 0)
        actor_io += execution.get('io', 0)
        actor_cpu += execution.get('cpu', 0)


    stats_store['summary']['total_executions_all'] += actor_exs
    stats_store['summary']['total_execution_runtime_all'] += actor_runtime
    stats_store['summary']['total_execution_io_all'] += actor_io
    stats_store['summary']['total_execution_cpu_all'] += actor_cpu
    if actor:
        stats_store['summary']['total_actors_all'] += 1
        stats_store['summary']['total_executions_existing'] += actor_exs
        stats_store['summary']['total_execution_runtime_existing'] += actor_runtime
        stats_store['summary']['total_execution_io_existing'] += actor_io
        stats_store['summary']['total_execution_cpu_existing'] += actor_cpu





def delete_from_summary(db_id):
    # this can't be tc, needs to be actual summary
    # for actor in delete list, do above logic but subtract
    # for actor_dbid, executions in executions_store.items():
    try:
        actor = Actor.from_db(stats_store[db_id])
    except KeyError:
        actor = None

    actor_exs = 0
    actor_runtime = 0
    actor_io = 0
    actor_cpu = 0

    actor_id = db_id.split('_')[1]
    executions = executions_store[actor_id]
    for ex_id, execution in executions.items():
        actor_exs -= 1
        actor_runtime -= execution.get('runtime', 0)
        actor_io -= execution.get('io', 0)
        actor_cpu -= execution.get('cpu', 0)

    stats_store['summary']['total_executions_all'] -= actor_exs
    stats_store['summary']['total_execution_runtime_all'] -= actor_runtime
    stats_store['summary']['total_execution_io_all'] -= actor_io
    stats_store['summary']['total_execution_cpu_all'] -= actor_cpu
    if actor:
        stats_store['summary']['total_actors_all'] -= 1
        stats_store['summary']['total_executions_existing'] -= actor_exs
        stats_store['summary']['total_execution_runtime_existing'] -= actor_runtime
        stats_store['summary']['total_execution_io_existing'] -= actor_io
        stats_store['summary']['total_execution_cpu_existing'] -= actor_cpu


if __name__ == '__main__':
    main()



# put actor status, once it's deleted, you don't have to compute again
# as going through the actors_store, go through first, have to do each time
# keep a list ids that you've seen; if these match in executions store, skip - can only do this if you keep a running total
# add them up to a single total, have a list of actor ids, can throw everything