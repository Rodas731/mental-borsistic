from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """
    Base class for all Market Intelligence Agents.
    Every agent should inherit from this and implement the 'analyze' method.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def analyze(self, ticker: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyzes data for a specific ticker and returns a signal.
        
        Args:
            ticker (str): The stock ticker symbol.
            data (Dict[str, Any]): Optional context/data provided by the Data Layer.
            
        Returns:
            Dict[str, Any]: A dictionary containing:
                - 'signal': float between -1.0 (strong sell) and 1.0 (strong buy)
                - 'confidence': float between 0.0 and 1.0
                - 'reasoning': str explaining the signal
                - 'metadata': dict with any additional context
        """
        pass
