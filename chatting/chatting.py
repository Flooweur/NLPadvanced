from pymongo import MongoClient
from datetime import datetime
import requests
import json

url = "http://localhost:1234/v1/chat/completions"
model = "llama-3.2-3b-instruct"
headers = {
    "Content-Type": "application/json"
}
client = MongoClient("mongodb://localhost:27017/")
db = client.test

# Prompt to create the context of the conversation / the conversation
def make_initial_prompt(agents, subject, location):
    descriptions = [f"Here is a description of {agent.name}: {agent.user_input}, {agent.gender}" for agent in agents]
    opinions = [f"Here is what {agent1.name} thinks about {agent2.name}:" + '''
            ''' + f"{agent1.opinions[agent2.name]}" for agent1 in agents for agent2 in agents if agent1 != agent2]
    agent1 = agents[0]
    message_content = f"""
            Context:
            {'''
            '''.join(descriptions)}
            {'''
            '''.join(opinions)}
            The context of this conversation is: {subject}
            Start directly by a quick sentence describing the scene{'' if location==None else "which is taking place at "+location}, what the agents were doing before starting the conversation and their main emotion, without an introduction.
            Then, create the conversation they had:

            {agent1.name}: "
        """
    return message_content

# Prompt to create a subject using the memory of a past conversation
def make_subject(memory):
    message_content = f"""
            Context:
            This is the memory of a conversation between 2 people:
            {memory}
            Make a summary in 1 sentence or 2 with the important points and details of the conversation (for example, if they are talking about doing an activity or a dish together, keep it in memory), ignorig the first sentence.
            Start directly with the summary, not with a phrase like "here is a summary".
        """
    return message_content

# Prompt to extract the emotion of an agent regarding the conversation and the importance of this conversation for the agent
def extract_emotion_and_importance(memory, agent_concerned):
    message_content = f"""
    Agent1: {agent_concerned.name}, {agent_concerned.gender}, {agent_concerned.user_input}
    Conversation: "{memory}"
    Possible emotions: ["happy", "sad", "angry", "neutral", "fearful"]
    Importance: On a scale of 1 to 10, 1 being very unimportant and mundane like a talk about the weather, 10 being very important like a breakup.

    Analyze the information about the agents and their conversation, and identify the primary emotion felt by Agent1 as well as the importance of the conversation as a result of this interaction.
    """ + """
    The response MUST be in the JSON format: {"emotion": "emotion", "importance": "importance"}. Here are a few examples of the format of the output:
    {"emotion": "happy", "importance": "10"}
    {"emotion": "sad", "importance": "5"}
    {"emotion": "neutral", "importance": "1"}
    {"emotion": "fearful", "importance": "3"}
    """
    return message_content

# Prompt to extract the opinion of an agent on a conversation (and another agent inside this conversation)
def extract_opinion(memory, agent_concerned, other, importance=0):
    message_content = f"""
    {agent_concerned.name}: {agent_concerned.gender}, {agent_concerned.user_input}
    {other.name}: {other.gender}, {other.user_input}
    Conversation: "{memory}"

    Here is the conversation that happened between {agent_concerned.name} and {other.name}.
    The importance of this conversation to the agent is {importance} on a scale of 1 to 10, 1 being very unimportant and mundane like a talk about the weather, 10 being very important like a breakup. You should take this into account to adjust how much you update their opinion.
    Summarize what {agent_concerned.name} thought about {other.name} in one short sentence. The sentence needs to be in third person:
    """
    return message_content

# Prompt to update the opinion of an agent regarding another one
# The opinion is update regarding a text (the extract opinion of the conversation or a memory) and an emotion (if given in argument)
# The intensity of the update also vary regarding the importance of the opinion.
def update_opinion(opinion, agent_concerned, other, emotion=None, importance=0):
    message_content = f"""
    {agent_concerned.name}: {agent_concerned.gender}, {agent_concerned.user_input}
    {other.name}: {other.gender}, {other.user_input}
    Last opinion of {agent_concerned.name} about {other.name}: {agent_concerned.opinions[other.name]}
    Analyzed phrase or conversation: "{opinion}"
    {f'Emotion felt by {agent_concerned.name}: "{emotion}"' if emotion else ''}

    Based on the information about both agents and the provided text, update the opinion of {agent_concerned.name} about {other.name}.
    If an emotion is specified, take it into account to adjust the tone or content of this opinion.
    The importance of this conversation to the agent is {importance} on a scale of 1 to 10, 1 being very unimportant and mundane like a talk about the weather, 10 being very important like a breakup. You should take this into account to adjust how much you update their opinion.
    If a part of the old opinion is correct, keep it in the new opinion.
    Juste give the new opinion, nothing else.
    """
    return message_content

# Prompt to extract the location of a conversation
def extract_location(memory):
    message_content = f"""
    Conversation: "{memory}"
    
    Based on the context of the conversation (the first sentence), extract the location of the interaction, in a single word.
    """
    return message_content

# Create a subject from the last memory of an agent
def create_subject_from_memory(memory):
    subject_prompt = make_subject(memory)
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": subject_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
        }
    response = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    subject = "Here is the resume of the last conversation: " + response + " They meet some time later."
    print("Subject :", subject)
    return subject

# Extract the location from the conversation of the agents
def extract_location_from_conversation(dialog):
    location_prompt = extract_location(dialog)
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": location_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
        }
    location = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    print("location:", location)
    return location

# Extract the emotion of the agent and the importance of this conversation for them
def extract_emotion_and_importance_from_conversation(dialog, agent_concerned):
    emotion_importance_prompt = extract_emotion_and_importance(memory=dialog, agent_concerned=agent_concerned)
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": emotion_importance_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
        }
    emotion = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    emotion_json = json.loads(emotion[emotion.find("{"):emotion.rfind("}")+1])
    
    # Decomment this if you want to see the reasons of the choices
    print(f"Emotion and importance for {agent_concerned.name} (+ reasons):", emotion, "\n")
    
    # Else, just use this one
    #print(f"Emotion of {agent_concerned.name}:{emotion_json['emotion']}, importance: {emotion_json['importance']}\n")
    return emotion_json

# Create an opinion for one agent regarding a conversation and another agent inside this conversation
# The importance of the dialog impact the opinion
def extract_opinion_from_conversation(dialog, agent_concerned, other, emotion_json, print_op = False):
    extract_prompt = extract_opinion(dialog, agent_concerned=agent_concerned, other=other, importance=emotion_json["importance"])
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": extract_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
        }
    opinion = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    
    if print_op:
        print(f"Opinion of {agent_concerned.name} about the conversation with {other.name}: {opinion}\n")
    return opinion

# Create an updated opinion of an agent regarding another one. The opinion, emotion and importance impact it.
def update_opinion_from_conversation(opinion, agent_concerned, other, emotion_json, print_update=False):
    update_prompt = update_opinion(opinion, agent_concerned=agent_concerned, other=other, emotion=emotion_json['emotion'], importance=emotion_json["importance"])
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": update_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
        }
    response = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    
    if print_update:
        print(f"New opinion of {agent_concerned.name} about {other.name}:{response}\n")
    
    return response

# Store a new memory inside the database
def store_memory(agent_id, agents_involved, importance, content, location, emotion):
    memory = {
        "agent_id": agent_id,
        "agents_involved": agents_involved,
        "timestamp": datetime.now(),
        "importance": importance,
        "content": content,
        "location": location,
        "emotion": emotion,
    }
    db.agent_memories.insert_one(memory)

# Store the new memory for all the agents regarding this new conversation
def store_all_memories(agents, memory):
    location = extract_location_from_conversation(dialog=memory)
    for agent in agents:
        others = [a for a in agents if a != agent]
        emotion_importance = extract_emotion_and_importance_from_conversation(dialog=memory, agent_concerned=agent)
        store_memory(agent_id=agent.agent_id, agents_involved=[o.agent_id for o in others], importance=int(emotion_importance['importance']),
                     content=str(memory), location=location, emotion=emotion_importance['emotion'])
        for other in others:
            extract_opinion = extract_opinion_from_conversation(dialog=memory, agent_concerned=agent, other=other, 
                                                                emotion_json=emotion_importance, print_op=True)
            update_opinion = update_opinion_from_conversation(opinion=extract_opinion, agent_concerned=agent, other=other,
                                                              emotion_json=emotion_importance, print_update=True)
            agent.opinions[other.name] = update_opinion
            
# Retrieve the memory of an agent
def retrieve_memories(agent_id):
    memories = db.agent_memories.find({
        "agent_id": agent_id
    }).sort("timestamp", -1)
    return list(memories)

# Retrieve all memories where agent_id appear (there memories and the memory of other agents)
def retrieve_memories_concerning(agent_id):
    memories = db.agent_memories.find({
        "$or": [
            {"agent_id": agent_id},
            {"agents_involved": agent_id}
        ]
    }).sort("timestamp", -1)
    return list(memories)

# Retreive the most recent memory shared by at least two agents of the list
def retrieve_most_recent_shared_memory(agent_ids):
    memories = db.agent_memories.find({
        "$and": [
            {"$or": [
                {"agent_id": {"$in": agent_ids}},
                {"agents_involved": {"$in": agent_ids}}
            ]},
            {"$expr": {"$gte": [
                {"$size": {"$setIntersection": [
                    {"$concatArrays": [
                        ["$agent_id"],
                        "$agents_involved"
                    ]},
                    agent_ids
                ]}},
                2
            ]}}
        ]
    }).sort("timestamp", -1)

    memories_list = list(memories)
    return memories_list[0] if memories_list else None

class Agent:
    def __init__(self, name, agent_id, user_input, gender):
        self.name = name
        self.agent_id = agent_id 
        self.user_input = user_input
        self.gender = gender
        self.opinions = {}
        
    def __str__(self):
        return f"Agent {self.name} (ID: {self.agent_id}) (Description: {self.user_input}) (Opinions: {self.opinions})"
    
    def name(self):
        return self.name
    
    def agent_id(self):
        return self.agent_id
    
    def user_input(self):
        return self.user_input
    
    def gender(self):
        return self.gender
    
# Create a chat between the agents, using the subject, the memory (if necessary) and a location (if given)
def chat(agents, subject, use_memory = True, use_location = None):
    memory = retrieve_most_recent_shared_memory([agent.agent_id for agent in agents])
    
    if (memory != None and use_memory):
        subject = create_subject_from_memory(memory=memory) + ' ' + subject
    
    message_prompt = make_initial_prompt(agents, subject, use_location)

    data = {
            "model": "llama-3.2-3b-instruct",
            "messages": [
                {"role": "system", "content": ""},
                {"role": "user", "content": message_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False
            }

    response = requests.post(url, headers=headers, json=data).json()["choices"][0]["message"]["content"]
    print(response)
    print("\n\n")

    store_all_memories(agents=agents, memory=response)
    return response