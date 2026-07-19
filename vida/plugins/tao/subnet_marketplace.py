"""Bittensor subnet registry — discoverable services and endpoints.

Each subnet on Bittensor offers a specific service type (compute, LLM, 
storage, etc.). Agents can query the registry to find services, check
pricing, and purchase access.

For now, this is a curated registry of known subnets with their API
endpoints and service descriptions. In the future, this could be
discovered dynamically from the chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ServiceType(Enum):
    """Type of service a subnet offers."""
    LLM_INFERENCE = "llm_inference"
    COMPUTE = "compute"
    STORAGE = "storage"
    IMAGE_GEN = "image_gen"
    AUDIO = "audio"
    VIDEO = "video"
    DATA = "data"
    AGENTS = "agents"
    CUSTOM = "custom"


@dataclass
class SubnetInfo:
    """Information about a Bittensor subnet."""
    netuid: int
    name: str
    description: str
    service_type: ServiceType
    api_endpoint: str = ""          # URL to reach the subnet's API
    api_type: str = "rest"           # rest, grpc, custom
    docs_url: str = ""               # API documentation
    pricing_model: str = "stake"     # "stake", "per_request", "subscription"
    estimated_cost_per_request: str = ""  # e.g., "0.001 TAO"
    requires_stake: bool = True      # Must stake to a subnet hotkey to use
    supported_models: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    health_endpoint: str = ""        # For checking subnet availability
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "netuid": self.netuid,
            "name": self.name,
            "description": self.description,
            "service_type": self.service_type.value,
            "api_endpoint": self.api_endpoint,
            "api_type": self.api_type,
            "docs_url": self.docs_url,
            "pricing_model": self.pricing_model,
            "estimated_cost_per_request": self.estimated_cost_per_request,
            "requires_stake": self.requires_stake,
            "supported_models": self.supported_models,
            "tags": self.tags,
        }


# ── Curated subnet registry ──
# Known subnets with verified service endpoints.
# Update as the ecosystem evolves.

SUBNET_REGISTRY: dict[int, SubnetInfo] = {
    # LLM / Text
    1: SubnetInfo(
        netuid=1, name="Omron (LLM)",
        description="Decentralized LLM inference — text generation, chat, completion",
        service_type=ServiceType.LLM_INFERENCE,
        api_endpoint="https://api.omron.ai/v1",
        docs_url="https://docs.omron.ai",
        pricing_model="per_request",
        estimated_cost_per_request="0.0001 TAO",
        supported_models=["llama-3", "mistral", "mixtral"],
        tags=["llm", "text", "chat"],
    ),
    9: SubnetInfo(
        netuid=9, name="Pretraining (LLM)",
        description="Distributed LLM pre-training — fine-tune models on subnet compute",
        service_type=ServiceType.COMPUTE,
        pricing_model="subscription",
        estimated_cost_per_request="varies by model size",
        tags=["compute", "training", "fine-tune"],
    ),
    19: SubnetInfo(
        netuid=19, name="Inference (LLM)",
        description="Open-source LLM inference — run models at cost",
        service_type=ServiceType.LLM_INFERENCE,
        api_endpoint="https://inference.subnet19.com/v1",
        docs_url="https://docs.subnet19.com",
        pricing_model="per_request",
        estimated_cost_per_request="0.00005 TAO",
        supported_models=["deepseek", "llama", "qwen", "phi"],
        tags=["llm", "inference", "open-source"],
    ),
    # Compute
    14: SubnetInfo(
        netuid=14, name="Compute (GPU)",
        description="Decentralized GPU compute — rent GPUs for ML workloads",
        service_type=ServiceType.COMPUTE,
        api_endpoint="https://api.compute14.ai/v1",
        docs_url="https://docs.compute14.ai",
        pricing_model="subscription",
        estimated_cost_per_request="0.01 TAO/hour",
        tags=["compute", "gpu", "ml"],
    ),
    # Storage
    27: SubnetInfo(
        netuid=27, name="Storage (Filecoin)",
        description="Decentralized storage — store and retrieve files",
        service_type=ServiceType.STORAGE,
        api_endpoint="https://api.subnet27.io/v1",
        docs_url="https://docs.subnet27.io",
        pricing_model="per_request",
        estimated_cost_per_request="0.0001 TAO per GB",
        tags=["storage", "filecoin", "decentralized"],
    ),
    # Image Generation
    34: SubnetInfo(
        netuid=34, name="Image Generation",
        description="AI image generation — text-to-image, image-to-image",
        service_type=ServiceType.IMAGE_GEN,
        api_endpoint="https://api.subnet34.ai/v1",
        docs_url="https://docs.subnet34.ai",
        pricing_model="per_request",
        estimated_cost_per_request="0.001 TAO",
        supported_models=["stable-diffusion", "flux", "dalle"],
        tags=["image", "generation", "ai"],
    ),
    # Audio
    3: SubnetInfo(
        netuid=3, name="Audio (TTS/STT)",
        description="Text-to-speech and speech-to-text services",
        service_type=ServiceType.AUDIO,
        api_endpoint="https://api.subnet3.io/v1",
        docs_url="https://docs.subnet3.io",
        pricing_model="per_request",
        estimated_cost_per_request="0.00005 TAO per minute",
        tags=["audio", "tts", "stt", "voice"],
    ),
    # Agents
    1: SubnetInfo(
        netuid=1, name="Agents (SN 1)",
        description="AI agent marketplace — deploy and query agents",
        service_type=ServiceType.AGENTS,
        api_endpoint="https://api.subnet1.ai/v1",
        pricing_model="per_request",
        estimated_cost_per_request="0.0005 TAO",
        tags=["agents", "autonomous", "ai"],
    ),
    # Data
    4: SubnetInfo(
        netuid=4, name="Data Scraping",
        description="Web scraping and data extraction services",
        service_type=ServiceType.DATA,
        api_endpoint="https://api.subnet4.io/v1",
        docs_url="https://docs.subnet4.io",
        pricing_model="per_request",
        estimated_cost_per_request="0.0001 TAO per 1000 pages",
        tags=["data", "scraping", "web"],
    ),
    # Video
    29: SubnetInfo(
        netuid=29, name="Video Generation",
        description="AI video generation — text-to-video, animation",
        service_type=ServiceType.VIDEO,
        api_endpoint="https://api.subnet29.ai/v1",
        docs_url="https://docs.subnet29.ai",
        pricing_model="per_request",
        estimated_cost_per_request="0.005 TAO",
        tags=["video", "generation", "ai"],
    ),
}


class SubnetRegistry:
    """Registry of known Bittensor subnets and their services.
    
    Agents use this to discover which subnets offer what services,
    check pricing, and find API endpoints.
    """
    
    @classmethod
    def list_all(cls) -> list[dict[str, Any]]:
        """List all known subnets."""
        return [info.to_dict() for info in SUBNET_REGISTRY.values()]
    
    @classmethod
    def get_by_netuid(cls, netuid: int) -> Optional[SubnetInfo]:
        """Get subnet info by netuid."""
        return SUBNET_REGISTRY.get(netuid)
    
    @classmethod
    def search(cls, service_type: Optional[ServiceType] = None,
               tags: Optional[list[str]] = None,
               query: str = "") -> list[dict[str, Any]]:
        """Search subnets by service type, tags, or name."""
        results = []
        for info in SUBNET_REGISTRY.values():
            if service_type and info.service_type != service_type:
                continue
            if tags:
                if not any(t in info.tags for t in tags):
                    continue
            if query:
                q = query.lower()
                if q not in info.name.lower() and q not in info.description.lower():
                    continue
            results.append(info.to_dict())
        return results
    
    @classmethod
    def find_by_capability(cls, capability: str) -> list[dict[str, Any]]:
        """Find subnets that offer a specific capability.
        
        Examples: "llm", "compute", "gpu", "image", "audio", "video"
        """
        capability = capability.lower()
        service_map = {
            "llm": ServiceType.LLM_INFERENCE,
            "text": ServiceType.LLM_INFERENCE,
            "chat": ServiceType.LLM_INFERENCE,
            "compute": ServiceType.COMPUTE,
            "gpu": ServiceType.COMPUTE,
            "storage": ServiceType.STORAGE,
            "image": ServiceType.IMAGE_GEN,
            "audio": ServiceType.AUDIO,
            "voice": ServiceType.AUDIO,
            "video": ServiceType.VIDEO,
            "data": ServiceType.DATA,
            "agent": ServiceType.AGENTS,
        }
        st = service_map.get(capability)
        if st:
            return cls.search(service_type=st)
        return cls.search(query=capability)
    
    @classmethod
    def stats(cls) -> dict[str, Any]:
        """Get registry statistics."""
        by_type: dict[str, int] = {}
        for info in SUBNET_REGISTRY.values():
            t = info.service_type.value
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_subnets": len(SUBNET_REGISTRY),
            "by_service_type": by_type,
            "pricing_models": list(set(
                info.pricing_model for info in SUBNET_REGISTRY.values()
            )),
        }