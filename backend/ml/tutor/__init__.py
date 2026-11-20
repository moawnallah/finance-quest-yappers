"""The tutor agent. Backend usage (docs/tutor_agent.md, section 5):

    from tutor import answer, TutorRequest, LiteLLMClient
    resp = answer(TutorRequest(mode="hint", user_id=uid, node="I2", task_id="i2.m1"), provider, LiteLLMClient())
    # store resp.event in llm_events; return resp.text, resp.links, resp.check_question, resp.hint_level
"""
from .llm import LiteLLMClient, RoleRefused, load_config
from .models import Completion, ContextProvider, LLMClient, TutorRequest, TutorResponse
from .pipeline import answer

__all__ = ["answer", "Completion", "ContextProvider", "LiteLLMClient", "LLMClient", "RoleRefused",
           "TutorRequest", "TutorResponse", "load_config"]
