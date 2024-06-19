from vja.apiclient import ApiClient
from vja.config import VjaConfiguration
from vja.output import Output
from vja.project_service import ProjectService
from vja.service_command import CommandService
from vja.service_query import QueryService
from vja.task_service import TaskService
from vja.urgency import Urgency

import caldav as cal
import pickle as pk
from config import cal_url, cal_username, cal_pass 
from os.path import isfile

syncpath = "sync/data"


"""
used for mapping the status of caldav and vikunja
backlog -> NEEDS-ACTION
to-do   -> NEEDS-ACTION
in-progress -> IN-PROCESS
completed  -> COMPLETED
"""
statuscache =     ["NEEDS-ACTION","NEEDS-ACTION", "IN-PROCESS", "COMPLETED"]
bucketnamecache = ["Backlog", "to-do", "in-progress", "completed"]

"""
bucketcache = {
    <projectid> : {
            <bucketid>: <name>,
            <bucketid>: <name>
        }
    }
"""
bucketcache = dict()


def getbucketname(queryservice, projectid, bucketid):
    """
    summary: grab the bucket name from vik and
    sends the caldav compatible status name
    args: 
        queryservice -> QueryService()
        projectid -> int
        bucketid -> int
    ret:
        bucket-name -> str
        [backlog, to-do, in-progress, completed]
    """
    if (projectid in bucketcache):
        try:
            bucketname = bucketcache[projectid][bucketid]
            return statuscache[bucketnamecache.index(bucketname)]
        except KeyError:
            return None
    else:
        bucketlist = queryservice.find_all_buckets_in_project(projectid)
        # populating the bucketcache
        temp = {}
        for bucket in bucketlist:
            temp[bucket.id] = bucket.title
        bucketcache[projectid] = temp
    return getbucketname(queryservice, projectid, bucketid)


if __name__ == "__main__":
    # setting up viknuja read more at: 
    # https://github.com/cernst72/vja/blob/main/vja/cli.py
    configuration = VjaConfiguration()
    api_client = ApiClient(configuration.get_api_url(), configuration.get_token_file())
    project_service = ProjectService(api_client)
    urgency_service = Urgency.from_config(configuration)
    task_service = TaskService(project_service, urgency_service)
    vja_command_service = CommandService(project_service, task_service, api_client)
    vja_query_service = QueryService(project_service, task_service, api_client)
    vja_output = Output()

    # querying the tasks that needed to be completed
    vja_task = vja_query_service.find_filtered_tasks(False, None, {})
    vja_output.task_array(vja_task, False, False, False)
    # list contains all the task that arent completed
    ongoing_task_list = [ (vja_task[task].id, vja_task[task].done) for task in range(0, len(vja_task)) ]
    # create a simple cache file with the 
    # states of the tasks;
    #does_file_exist = isfile(syncpath)
    #if does_file_exist: 
    #    with open(syncpath, 'rb') as f:
    #        previous_task_list = pk.load(f)
    #    # comparing the current task with the previous
    #    # tasks and check if any updates are necessary
    #    updated_task_list = set(previous_task_list)^set(current_task_list)
    #    # if differences are present dump them into the new file
    #    if (updated_task_list): 
    #        with open(syncpath, 'wb') as f:
    #            pk.dump(current_task_list, f)
    #    else:
    #        print("nothing to update")
    #        exit(0)
    #else:
    #    # this means that the file doesn't exist
    #    # we will create a new file later
    #    with open(syncpath, 'wb') as f:
    #        pk.dump(current_task_list, f)

    with cal.DAVClient(
            url=cal_url, username=cal_username, 
            password=cal_pass) as client:
        # TODO: fix this lmao; i am physically
        # selecting the calendar; i know the calendar url
        # just add comparison or something
        my_principal = client.principal()
        task_calendar = my_principal.calendars()[-1]
        todo_list = []
        # iterate through the task; calendar and 
        # create a list with the incompleted task
        for task in task_calendar.search():
            # grabbing all the incomplete task;
            # the title has the vikid
            # (vikid) <taskname>
            if task.data.find("STATUS:COMPLETED") == -1:
                # grabbing the vik-id
                try:
                    vikid = int(task.data[task.data.find("SUMMARY"):].split("\n")[0].split("-")[-1].strip())
                    todo_list.append((vikid,task))
                except ValueError:
                    continue
        # generating a list with only vikunja id
        todo_list_vja_id = [i for (i,j) in todo_list]
        for i in range(0, len(vja_task)):
            task = vja_task[i]
            title = f"{task.title}-{task.id}"
            due = task.due_date
            status = getbucketname(vja_query_service , task.project.id, task.bucket_id) 
            if task.id in todo_list_vja_id:
                # entry already present 
                task_in_task_calendar = todo_list[todo_list_vja_id.index(task.id)][1]
                if status == "completed":
                    task_in_task_calendar.complete()
            else:
                # add the new entry into the caldav
                task_calendar.save_todo(
                    summary=title,
                    due= task.due_date,
                    status=status
                )
