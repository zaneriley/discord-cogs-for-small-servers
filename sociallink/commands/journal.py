import openai

openai.api_key = "sk-proj-4zEk2OyO6yeOHw5bAXhMT3BlbkFJh8ffc36JgAVCJGPyZmzO"

async def generate_journal_description(self, event_type, initiator_id, confidant_id, details):
    prompt = f"""
    Given a dialogue with a friend, classify the dialogue as being associated with a certain level and provide a concise 1 sentence summary of the dialogue, focusing on the NPC/friend's connection growing. Write in 2nd person. Write in the style of Persona 5.

    Example 1:
    Friend: Ryuichi
    Dialogue:
    "But for some reason it don't look like he's gettin' along with the others." Nakaoka? "It's good they're keepin' their heads low now though. I don't want 'em endin' up like me." But you're doing great.
    Level: 4
    Summary: "Though still worried about the track team, Ryuichi said he has the Phantom Thieves now."

    Example 2:
    Friend: Sakamoto
    Dialogue:
    "You're not causing any trouble, are you?" I'm not. "If you could lend a hand, it'd really be a great help..." I'd be glad to. "I'll teach you how to make the perfect cup of coffee. Not a bad trade, eh?" I guess.
    Level: 1
    Summary: "Something about the smell of coffee, and "her"..."

    Example 3:
    Friend: Yoshida
    Dialogue:
    "Okay, I'm going to get started." Do your best. "Perhaps, it's the effect of you moving my heart." What are you talking about?
    Level: 9
    Summary: "Yoshida mentioned nothing about the false charge, which moves his colleague to support his run."

    Friend: User {confidant_id}
    Dialogue:
    {details}
    Level: {level}
    Summary:
    """

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100,
        n=1,
        stop=None,
        temperature=0.7,
    )

    return response.choices[0].text.strip()


async def _sanitize_journal_inputs(content):
    # Strip unnecessary discord garbage from the content
    return content