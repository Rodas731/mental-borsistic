from typing import List, Dict
from loguru import logger

class SignalFusionEngine:
    """
    Aggregates signals from multiple agents to produce a final prediction.
    """
    def __init__(self):
        # We can assign different weights to agents based on historical performance
        self.weights = {
            "Price/Momentum Agent": 1.5,
            "News/NLP Agent": 1.0,
            "SEC Fundamentals Agent": 1.0,
            "Smart Money Agent": 1.2
        }

    def fuse_signals(self, signals) -> Dict:
        """
        Accepts either a dict of agent results or a list of agent results and delegates to process_signals.
        """
        if isinstance(signals, dict):
            agent_results = list(signals.values())
        elif isinstance(signals, list):
            agent_results = signals
        else:
            agent_results = []
        return self.process_signals(agent_results)

    def process_signals(self, agent_results: List[Dict]) -> Dict:
        """
        Takes a list of agent results and calculates a fused signal.
        Each agent result must contain: 'agent_name', 'signal', 'confidence', 'reasoning'.
        """
        logger.info("Fusing signals...")
        
        if not agent_results:
            return {"final_signal": 0.0, "prediction": "NEUTRAL", "confidence": 0.0, "details": {}}
            
        total_weighted_signal = 0.0
        total_weight = 0.0
        
        for result in agent_results:
            name = result.get('agent_name', 'Unknown')
            signal = result.get('signal', 0.0)
            conf = result.get('confidence', 0.0)
            
            # Base weight defined in config, times the agent's confidence
            weight = self.weights.get(name, 1.0) * conf
            
            total_weighted_signal += signal * weight
            total_weight += weight
            
        if total_weight == 0:
            return {"final_signal": 0.0, "prediction": "NEUTRALE", "confidence": 0.0, "details": agent_results}
            
        final_signal = total_weighted_signal / total_weight
        
        # Extract Risk Level
        risk_level = "SCONOSCIUTO"
        risk_score = 0.0
        for r in agent_results:
            if r.get('agent_name') == "Risk Analyst Agent":
                risk_level = r.get('metadata', {}).get('risk_level', "SCONOSCIUTO")
                risk_score = r.get('metadata', {}).get('risk_score', 0.0)

        # Extract Macro Multiplier
        macro_multiplier = 1.0
        macro_reasoning = ""
        for r in agent_results:
            if r.get('agent_name') == "Macro Analyst Agent":
                macro_multiplier = r.get('signal', 1.0)
                macro_reasoning = r.get('reasoning', "")
                
        # Apply multiplier to positive signals (or all signals)
        if final_signal > 0:
            final_signal *= macro_multiplier
            
        # Determine prediction category
        if final_signal >= 0.2:
            prediction = "RIALZISTA"
        elif final_signal <= -0.2:
            prediction = "RIBASSISTA"
        else:
            prediction = "NEUTRALE"
            
        # Overall confidence could be the average confidence of agents
        # We exclude Risk Analyst Agent and Macro Analyst Agent from confidence average if it's there
        directional_agents = [r for r in agent_results if r.get('agent_name') not in ["Risk Analyst Agent", "Macro Analyst Agent"]]
        if directional_agents:
            overall_confidence = sum(r.get('confidence', 0) for r in directional_agents) / len(directional_agents)
        else:
            overall_confidence = 0.0
            

        
        return {
            "final_signal": float(final_signal),
            "prediction": prediction,
            "confidence": float(overall_confidence),
            "risk_level": risk_level,
            "risk_score": float(risk_score),
            "details": agent_results
        }
