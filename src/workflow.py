import httpx
import aiohttp

from log import getlogger
from api import edit_message, send_message_as_tool

logger = getlogger()

async def workflow_steps(
        superagent_url: str,
        workflow_id: str,
        api_key: str,
        session: httpx.AsyncClient
):
    headers = {
        'Authorization': f'Bearer {api_key}',
    }
    api_url = f"{superagent_url}/api/v1/workflows/{workflow_id}/steps"
    response = await session.get(
        api_url,
        headers=headers,
        timeout=30,
    )
    result = {}
    if response.status_code == 200:
        data = response.json()["data"]
        for agents in data:
            agent_id = agents['agent']['id']
            agent_name = agents['agent']['name']
            result[agent_name] = agent_id

        return result
    return response.json()


async def workflow_invoke(
    superagent_url: str,
    workflow_id: str,
    prompt: str,
    api_key: str,
    session: httpx.AsyncClient,
    sessionId: str,
    userEmail: str = None,
) -> str:
    """
    Sends a query to the Superagent API and returns the response.

    Args:
        api_url (str): The URL of the superagent API.
        prompt (str): The question to ask the API.
        session (aiohttp.ClientSession): The aiohttp session to use.
        sessionId (str) : Matrix Room id to manage sessions.
        headers (dict, optional): The headers to use. Defaults to None.

    Returns:
        str: The response from the API.
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
    }
    json_body = {
        "input": prompt,
        "sessionId": sessionId,
        "enableStreaming": False,
    }
    api_url = f"{superagent_url}/api/v1/workflows/{workflow_id}/invoke"
    if userEmail:
        json_body["userEmail"] = userEmail
    logger.info(json_body)
    response = await session.post(
        superagent_url,
        json=json_body,
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
        data = response.json()['data']
        logger.info(f"json body: {json_body}")
        return data['output']
    return "Error!"


async def stream_workflow(
    api_url,
    api_key,
    workflow_id,
    msg_data,
    agent,
    thread_id,
    reply_id,
    room_id,
    session: httpx.AsyncClient,
    workflow_bot=None,
    user_email=None,
    msg_limit=0,
    single_bot=False
):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    json = {"input": msg_data, "sessionId": thread_id,
            "enableStreaming": True, "stream_token": True}
    api_path = f"{api_url}/api/v1/workflows/{workflow_id}/invoke"
    if user_email:
        json["userEmail"] = user_email
    logger.info(f"stream json : {json}")
    prev_data = ''
    access_token = None
    lines = 0
    prev_event = list(agent.keys())[0]
    async with aiohttp.ClientSession() as session:
        async with session.post(api_path, headers=headers, json=json) as response:
            response.raise_for_status()
            async for line in response.content:
                data = line.decode('utf-8')
                # Split the line into event and data parts
                if data.startswith("workflow_agent_name:"):
                    event = data.split("name:")[1][:-1]
                    if prev_event != event:
                        prev_event = event
                        lines = 0
                        await edit_message(event_id, access_token, prev_data, room_id, workflow_bot, msg_limit, thread_id)
                        prev_data = ''
                        access_token = None
                elif data.startswith("event: function_call"):
                    pass
                else:
                    prev_data += data
                    lines += 1
                    if access_token is None:
                        logger.info(f"single_bot: workflow invoke {single_bot}")
                        msg_content = str(agent[prev_event]) + prev_data
                        msg_data = await send_agent_message(workflow_id, thread_id, reply_id, msg_content, room_id, workflow_bot, msg_limit)
                        event_id, access_token = msg_data
                    elif lines % 5 == 0:
                        await edit_message(event_id, access_token, prev_data, room_id, workflow_bot, msg_limit, thread_id)

    # Print the complete message for the last event
    if prev_event is not None:
        logger.info(f'Event: {prev_event}, Data: {prev_data}')
        await edit_message(event_id, access_token, prev_data, room_id, workflow_bot, msg_limit, thread_id)
    else:
        logger.info('Failed to fetch streaming data')


async def send_agent_message(agent, thread_event_id, reply_id, data, room_id, workflow_bot=None, msg_limit=0):
    thread = {
        'rel_type': 'm.thread',
        'event_id': thread_event_id,
        'is_falling_back': True,
        'm.in_reply_to': {'event_id': reply_id}
    }
    data = await send_message_as_tool(agent, data, room_id, reply_id, thread, workflow_bot, msg_limit, session_id=thread_event_id)
    return data
