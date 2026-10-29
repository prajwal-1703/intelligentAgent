import os
import webbrowser
import subprocess

class ActionExecutor:
    def __init__(self, memory_storage, vis_controller=None):
        self.memory = memory_storage
        self.vis_controller = vis_controller

    def execute(self, action: dict) -> str:
        intent = action.get("intent")
        
        if intent == "open_app":
            return self._open_app(action.get("app", ""))
            
        elif intent == "open_website":
            url = action.get("url", "")
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            return f"Opening website {url}"
            
        elif intent == "search_google":
            query = action.get("query", "")
            url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
            return f"Searching Google for {query}"
            
        elif intent == "watch_video":
            query = action.get("query", "")
            url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(url)
            return f"Searching YouTube for {query}"
            
        elif intent == "remember_info":
            text = action.get("text", "")
            self.memory.remember(text)
            return "Got it, I've stored that in my memory."
            
        elif intent == "recall_info":
            query = action.get("query", "")
            res = self.memory.recall(query)
            return f"Memory recall: {res}"
            
        elif intent == "visualize":
            metric = action.get("metric", "cpu")
            msg = action.get("message", "Visualizing metric.")
            if self.vis_controller:
                self.vis_controller.show_visualization(metric)
            return msg

        elif intent == "chat":
            return action.get("message", "I am here.")
            
        elif intent == "analyze_screen":
            # Handled uniquely in the main orchestrator due to screen capture flow,
            # but if it lands here, do nothing but reply
            return action.get("explanation", "I have analyzed the screen.")

        else:
            return f"Unknown intent: {intent}"

    def _open_app(self, app_name: str) -> str:
        # A simple heuristic based on windows common apps
        # For a full production system, use windows registry to find exes
        app_name = app_name.lower().strip()
        
        shortcuts = {
            "chrome": "start chrome",
            "brave": "start brave",
            "edge": "start msedge",
            "notepad": "notepad",
            "calculator": "calc",
            "vs code": "code",
            "vscode": "code",
            "explorer": "explorer"
        }
        
        cmd = shortcuts.get(app_name)
        if cmd:
            subprocess.Popen(cmd, shell=True)
            return f"Opened {app_name}"
        else:
            # Fallback to start <app_name>
            subprocess.Popen(f"start {app_name}", shell=True)
            return f"Attempted to open {app_name}"
