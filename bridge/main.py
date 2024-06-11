from vja.apiclient import ApiClient
from vja.config import VjaConfiguration
from vja.output import Output
from vja.project_service import ProjectService
from vja.service_command import CommandService
from vja.service_query import QueryService
from vja.task_service import TaskService
from vja.urgency import Urgency

import caldav as cal


if __name__ == "__main__":
#    with caldav.DAVClient(url=cal_url, username=cal_username, password=cal_password) as client:
#        my_principal = client.principal()

    # cofiguring viknuja setup 
    # read more at https://github.com/cernst72/vja/blob/main/vja/cli.py
    configuration = VjaConfiguration()
    api_client = ApiClient(configuration.get_api_url(), configuration.get_token_file())
    project_service = ProjectService(api_client)
    urgency_service = Urgency.from_config(configuration)
    task_service = TaskService(project_service, urgency_service)
    vja_command_service = CommandService(project_service, task_service, api_client)
    vja_query_service = QueryService(project_service, task_service, api_client)

    # querying the tasks that needed to be completed
    vja_task = vja_query_service.find_filtered_tasks(False, None, {})
