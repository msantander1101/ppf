import importlib
import traceback
from typing import Any, Dict

class Engine:
    """
    Motor central que ejecuta módulos OSINT.
    Cada módulo se carga dinámicamente desde modules/.
    """

    def __init__(self):
        self.results = {}

    def run_module(self, module_path: str, **kwargs) -> Dict[str, Any]:
        try:
            mod = importlib.import_module(module_path)
            if hasattr(mod, "run"):
                result = mod.run(**kwargs)
                self.results[module_path] = result
                return result
            else:
                raise AttributeError(f"El módulo {module_path} no tiene función 'run'")
        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}

engine = Engine()