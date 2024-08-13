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
import sys


syncpath = "sync"

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
    
    vja_task_ongoing = list()
    vja_task_completed = list()

    # querying the tasks that needed to be completed
    task_ongoing = vja_query_service.find_filtered_tasks(False, None, {})
    for t in task_ongoing:
        if t.project.title == "Inbox":
            vja_task_ongoing.append(t)
    # currently vja_task_completed doesn't work
    task_completed = vja_query_service.find_filtered_tasks(True, None, {})
    for t in task_ongoing:
        if t.project.title == "Inbox":
            vja_task_completed.append(t)
    # create a simple cache file with the 
    # states of the tasks;
    does_file_exist = isfile(syncpath)
    if does_file_exist: 
        with open(syncpath, 'rb') as f:
            previous_ongoing_task_list = pk.load(f)
            prev_ongoing_task_list = [ previous_ongoing_task_list[task].id \
                    for task in range(0, len(previous_ongoing_task_list)) ]
    else:
        print("no sync file is present; creating a new file")
        # file doesn't exist, create a new file later
        with open(syncpath, 'wb') as f:
            pk.dump(vja_task_ongoing, f)
        prev_ongoing_task_list = []

    ongoing_task_list = [ vja_task_ongoing[task].id for task in range(0, len(vja_task_ongoing)) ]
    with open(syncpath, 'wb') as f:
        pk.dump(vja_task_ongoing, f)

    new_task = list(set(ongoing_task_list) - set(prev_ongoing_task_list))
    # assuming that the task not present in the ongoing task list is either completed
    # or deleted; these task will be marked as completed in caldav
    completed_task = list(set(prev_ongoing_task_list) - (set(ongoing_task_list)))

    print(f"detected {len(new_task)} new task")
    print(f"detected {len(completed_task)} completed task")

    if ((len(new_task) == 0) and (len(completed_task) == 0)):
        sys.exit()

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
                    print("value error")
                    continue
        # generating a list with only vikunja id
        todo_list_vja_id = [i for (i,j) in todo_list]
        for i in range(0, len(new_task)):
            task = vja_query_service.find_task_by_id(new_task[i])
            title = f"{task.title}-{task.id}"
            due = task.due_date
            status = getbucketname(vja_query_service , task.project.id, task.bucket_id) 
            if task.id not in todo_list_vja_id:
                # add the new entry into the caldav
                print(f"adding entry -> {title}")
                task_calendar.save_todo(
                    summary=title,
                    due= task.due_date,
                    status=status
                )
        for i in range(0, len(completed_task)):
            task = vja_query_service.find_task_by_id(completed_task[i])
            title = f"{task.title}-{task.id}"
            if task.id in todo_list_vja_id:
                print(f"marking -> {title} as completed")
                task_in_task_calendar = todo_list[todo_list_vja_id.index(task.id)][1]
                task_in_task_calendar.complete()
