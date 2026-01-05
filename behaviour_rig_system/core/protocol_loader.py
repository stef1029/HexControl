"""
Protocol Loader

Creates protocol classes from simple definitions. A protocol file just needs:

    NAME = "My Protocol"
    DESCRIPTION = "What it does"
    
    PARAMETERS = {
        "num_trials": {"default": 10, "label": "Number of Trials"},
        "led_duration": {"default": 1.0, "label": "LED Duration (s)"},
    }
    
    def run(link, params, log, check_abort):
        '''
        link: BehaviourRigLink - use link.led_set(), link.valve_pulse(), etc.
        params: Dict of parameter values from GUI
        log: Function to print to GUI log
        check_abort: Function that returns True if user clicked Stop
        '''
        for trial in range(params["num_trials"]):
            if check_abort():
                return
            log(f"Trial {trial + 1}")
            link.led_set(0, 255)
            time.sleep(params["led_duration"])
            link.led_set(0, 0)
"""

from core.protocol_base import BaseProtocol, ProtocolEvent
from core.parameter_types import IntParameter, FloatParameter, BoolParameter


def create_protocol_class(name: str, description: str, parameters: dict, run_func) -> type:
    """
    Create a protocol class from simple components.
    
    Args:
        name: Protocol name for GUI tab
        description: Description shown in GUI
        parameters: Dict like {"param_name": {"default": 10, "label": "My Param"}}
        run_func: Function with signature run(link, params, log, check_abort)
    
    Returns:
        A BaseProtocol subclass ready for the GUI
    """
    
    # Convert simple parameter dict to Parameter objects
    param_objects = []
    for param_name, config in parameters.items():
        default = config.get("default", 0)
        label = config.get("label", param_name)
        
        if isinstance(default, bool):
            param_objects.append(BoolParameter(
                name=param_name, 
                display_name=label, 
                default=default
            ))
        elif isinstance(default, float):
            param_objects.append(FloatParameter(
                name=param_name, 
                display_name=label, 
                default=default,
                min_value=config.get("min"),
                max_value=config.get("max"),
            ))
        else:
            param_objects.append(IntParameter(
                name=param_name, 
                display_name=label, 
                default=int(default),
                min_value=config.get("min"),
                max_value=config.get("max"),
            ))
    
    class GeneratedProtocol(BaseProtocol):
        """Auto-generated protocol from simple definition."""
        
        @classmethod
        def get_name(cls) -> str:
            return name
        
        @classmethod
        def get_description(cls) -> str:
            return description
        
        @classmethod
        def get_parameters(cls) -> list:
            return param_objects
        
        def _cleanup(self) -> None:
            # Turn off all outputs on cleanup
            if self.link:
                try:
                    self.link.shutdown()
                except Exception:
                    pass
        
        def _on_abort(self) -> None:
            # Turn off all outputs on abort
            if self.link:
                try:
                    self.link.shutdown()
                except Exception:
                    pass
        
        def _run_protocol(self) -> None:
            # Simple log function
            def log(msg: str):
                self._emit_event(ProtocolEvent("status_update", data={"message": msg}))
            
            # Run user's function with direct BehavLink access
            run_func(
                self.link,          # BehaviourRigLink (raw hardware control)
                self.parameters,    # Parameter values dict
                log,                # log(msg) function
                self._check_abort,  # check_abort() function
            )
    
    return GeneratedProtocol
