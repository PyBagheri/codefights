# TODO: Add logging + tests

import os
import sys

# This module is not meant to be imported.
if __name__ != '__main__':
    exit(1)

# The one and only argument must be the worker name,
# which will also be used as the redis consumer name.
if len(sys.argv) != 2:
    exit(1)

WORKER_NAME = sys.argv[1]

import redis.asyncio as redis
import asyncio
import json
import importlib


import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

django.setup()


from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async

from common.values import TerminationReasons
from games._base.report import VictoryDrawResult

from fights.models import Fight, PlayerFight
from gamespecs.models import GameInfo, GameResult

# Cache
ConclusionSystems = GameInfo.ConclusionSystems


# The config file can be either inside the docker container
# as a docker config, or out of docker in the project root.
# This is so that we can run this both with and without docker.
os.environ.setdefault('GLOBAL_CONFIG_MODULE', 'config')

global_config = importlib.import_module(os.environ.get('GLOBAL_CONFIG_MODULE'))


# We'll want everything in text form, so enable auto-decoding.
redis_client = redis.from_url(global_config.REDIS_SERVER_URL,
                              decode_responses=True)


# Since transactions aren't supported in async context in Django,
# we have to use sync_to_async().
@transaction.atomic
def save_to_db(fight, game_result, playerfights):
    game_result.save()
    
    fight.save()
    
    PlayerFight.objects.bulk_update(playerfights, [
        'termination_reason',
        'termination_reason_extra',
        'final_waitpid_state',
        'won_or_rank',
        'score'
    ])


async def process(message):
    message_id, serialized_data = message
    
    data = json.loads(serialized_data['data'])
    
    fight_id = data['fight_id']
    report = data['report']
    final_states = data['final_states']
    
    fight = await Fight.objects.select_related(
        'game'
    ).only(
        'game__conclusion_system',
        'game__has_scores'
    ).aget(id=fight_id)
    
    # The ordering is to know which index belongs to which player.
    # We cannot use .update() directly, as it doesn't support ordering.
    playerfights = fight.playerfight_set.only('id').order_by('id')
    
    if fight.game.has_scores:
        result, scores, explanation, data = report
    else:
        result, explanation, data = report
    
    
    # Since "async for" and "enumerate()" are not compatible,
    # we have to hold the index manually.
    index = 0
    async for pf in playerfights:
        fs = final_states[index]
        
        if fs == 0:
            pf.final_waitpid_state = 0
        else:  # the player was terminated.
            termination_reason, termination_explanation = fs
            pf.termination_reason = termination_reason
            
            # In case of an illegal syscall, we return a list of 3
            # numbers (the syscall number, the 1st and the 2nd args),
            # but in other cases, the termination explanation is either
            # the waitpid status, or nothing (when we don't have access
            # to any waitpid state).
            if termination_reason == TerminationReasons.ILLEGAL_SYSCALL:
                pf.termination_reason_extra = termination_explanation
            elif termination_explanation:
                pf.final_waitpid_state = termination_explanation
        
        index += 1
    
    # Since the playerfights queryset is already evaluated, we don't need
    # to use 'async for' hereafter.
    
    match fight.game.conclusion_system:
        case ConclusionSystems.VICTORY_DRAW:
            if result != VictoryDrawResult.DRAW:
                for index, pf in enumerate(playerfights):
                    pf.won_or_rank = (
                        1 if result[index] == VictoryDrawResult.WINNER else 0
                    )

        case ConclusionSystems.RANK_BASED:
            for index, pf in enumerate(playerfights):
                pf.won_or_rank = result[index]
    
    
    if fight.game.has_scores:
        for index, pf in enumerate(playerfights):
            pf.score = scores[index]
    
    
    fight.finished_at = timezone.now()

    
    game_result = GameResult(
        fight=fight,
        explanation=(json.dumps(explanation) if explanation else ''),
        data=json.dumps(data)  # may never be empty
    )
    
    await sync_to_async(save_to_db)(fight, game_result, playerfights)
    
    await redis_client.xack(global_config.REDIS_RESULT_PROCESSOR_STREAM,
                            global_config.REDIS_RESULT_PROCESSOR_GROUP,
                            message_id)



async def process_unacked():
    # The worker might crash while some results have not
    # been acknowledged yet (which shouldn't really be
    # more than one per worker). We redo those simulations.
    unacked = (await redis_client.xreadgroup(
            groupname=global_config.REDIS_RESULT_PROCESSOR_GROUP,
            consumername=WORKER_NAME,
            streams={global_config.REDIS_RESULT_PROCESSOR_STREAM: '0'},
    ))[0][1]  # get for the one and only relevant stream.

    for msg in unacked:
        await process(msg)


async def process_forever():
    while True:
        query = (await redis_client.xreadgroup(
            groupname=global_config.REDIS_RESULT_PROCESSOR_GROUP,
            consumername=WORKER_NAME,
            streams={global_config.REDIS_RESULT_PROCESSOR_STREAM: '>'},  # only the new messages
            block=0,  # block until a new message arrives.
            count=1
        ))[0]  # get for the one and only relevant stream.
                
        # Process the one and only message.
        await process(query[1][0])


async def main():
    await process_unacked()
    await process_forever()  # will never stop

asyncio.run(main())
