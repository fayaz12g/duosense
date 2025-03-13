import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import threading
import time
import logging
from virtualcontroller import VirtualController
import sys
import os
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('controller_merger.log')
    ]
)
logger = logging.getLogger(__name__)

class ControllerMerger:
    def __init__(self, root):
        self.root = root
        self.root.title("DualSense Controller Merger")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Initialize virtual controller
        self.virtual_controller = VirtualController()

        # Initialize pygame for controller handling
        pygame.init()
        pygame.joystick.init()
        
        # Variables
        self.is_running = False
        self.controllers = []
        self.player1_id = None
        self.player2_id = None
        self.combined_state = defaultdict(bool)
        self.combined_axes = defaultdict(float)
        
        # Player input states
        self.player1_inputs = defaultdict(bool)
        self.player1_axes = defaultdict(float)
        self.player2_inputs = defaultdict(bool)
        self.player2_axes = defaultdict(float)
        
        # Create UI
        self.create_ui()
        
        # Start controller detection thread
        self.detection_thread = threading.Thread(target=self.detect_controllers, daemon=True)
        self.detection_thread.start()
        
        # Update UI periodically
        self.root.after(100, self.update_ui)

    def create_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Controller selection section
        selection_frame = ttk.LabelFrame(main_frame, text="Controller Selection", padding="10")
        selection_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Player 1 selection
        ttk.Label(selection_frame, text="Player 1:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.p1_combo = ttk.Combobox(selection_frame, state="readonly", width=40)
        self.p1_combo.grid(row=0, column=1, padx=5, pady=5)
        self.p1_combo.bind("<<ComboboxSelected>>", self.on_p1_selected)
        
        # Player 2 selection
        ttk.Label(selection_frame, text="Player 2:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.p2_combo = ttk.Combobox(selection_frame, state="readonly", width=40)
        self.p2_combo.grid(row=1, column=1, padx=5, pady=5)
        self.p2_combo.bind("<<ComboboxSelected>>", self.on_p2_selected)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="Start Merging", command=self.start_merging)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_merging, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Visualization frame
        viz_frame = ttk.LabelFrame(main_frame, text="Controller Visualization", padding="10")
        viz_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create three canvases side by side
        canvas_frame = ttk.Frame(viz_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Player 1 canvas
        p1_frame = ttk.LabelFrame(canvas_frame, text="Player 1")
        p1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.p1_canvas = tk.Canvas(p1_frame, width=200, height=300, bg="white")
        self.p1_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Player 2 canvas
        p2_frame = ttk.LabelFrame(canvas_frame, text="Player 2")
        p2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.p2_canvas = tk.Canvas(p2_frame, width=200, height=300, bg="white")
        self.p2_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Combined output canvas
        combined_frame = ttk.LabelFrame(canvas_frame, text="Combined Output")
        combined_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.combined_canvas = tk.Canvas(combined_frame, width=200, height=300, bg="white")
        self.combined_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = tk.Text(log_frame, height=10, width=70)
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Set up custom logging handler to redirect to text widget
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record)
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END)
                
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(text_handler)
        
        # Draw initial controller states
        self.draw_controller(self.p1_canvas, {}, {})
        self.draw_controller(self.p2_canvas, {}, {})
        self.draw_controller(self.combined_canvas, {}, {})

    def detect_controllers(self):
        # Thread function to detect connected controllers
        while True:
            # Get current controller count
            pygame.joystick.quit()
            pygame.joystick.init()
            
            current_controllers = []
            for i in range(pygame.joystick.get_count()):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    joystick.init()
                    current_controllers.append({
                        "id": i,
                        "name": joystick.get_name(),
                        "guid": joystick.get_guid(),
                        "joystick": joystick
                    })
                except pygame.error as e:
                    logger.error(f"Error initializing controller {i}: {e}")
            
            # Update controller list
            self.controllers = current_controllers
            
            # Sleep for a bit before checking again
            time.sleep(1)

    def update_ui(self):
        # Update UI elements - called periodically
        # Update controller lists
        controllers_list = ["None"] + [f"{c['id']}: {c['name']}" for c in self.controllers]
        
        current_p1 = self.p1_combo.get()
        current_p2 = self.p2_combo.get()
        
        self.p1_combo['values'] = controllers_list
        self.p2_combo['values'] = controllers_list
        
        # Maintain selections if they're still valid
        if current_p1 in controllers_list:
            self.p1_combo.set(current_p1)
        elif self.p1_combo.get() == "":
            self.p1_combo.set("None")
            
        if current_p2 in controllers_list:
            self.p2_combo.set(current_p2)
        elif self.p2_combo.get() == "":
            self.p2_combo.set("None")
        
        # If we're running, update the controller states
        if self.is_running:
            self.update_controller_states()
            
            # Draw controller states
            self.draw_controller(self.p1_canvas, self.player1_inputs, self.player1_axes)
            self.draw_controller(self.p2_canvas, self.player2_inputs, self.player2_axes)
            self.draw_controller(self.combined_canvas, self.combined_state, self.combined_axes)
        
        # Schedule the next update
        self.root.after(50, self.update_ui)

    def on_p1_selected(self, event):
        # Handle player 1 controller selection
        selection = self.p1_combo.get()
        if selection == "None":
            self.player1_id = None
            logger.info("Player 1 controller unassigned")
        else:
            self.player1_id = int(selection.split(":")[0])
            logger.info(f"Player 1 assigned to controller {self.player1_id}")

    def on_p2_selected(self, event):
        # Handle player 2 controller selection
        selection = self.p2_combo.get()
        if selection == "None":
            self.player2_id = None
            logger.info("Player 2 controller unassigned")
        else:
            self.player2_id = int(selection.split(":")[0])
            logger.info(f"Player 2 assigned to controller {self.player2_id}")

    def start_merging(self):
        # Start the controller merging process
        if self.player1_id is None and self.player2_id is None:
            messagebox.showwarning("Warning", "Please select at least one controller")
            return
    
        # Initialize the virtual controller
        if not self.virtual_controller.is_initialized:
            messagebox.showwarning("Warning", "Virtual controller could not be initialized")
            logger.error("Failed to start: Virtual controller not initialized")
            return
    
        # Start the virtual controller
        success = self.virtual_controller.start()
        if not success:
            messagebox.showerror("Error", "Failed to start virtual controller")
            return
        
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start the merger thread
        self.merger_thread = threading.Thread(target=self.merger_loop, daemon=True)
        self.merger_thread.start()
        
        logger.info("Controller merging started")

    # Modify the stop_merging method
    def stop_merging(self):
        # Stop the controller merging process
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Stop the virtual controller
        self.virtual_controller.stop()
        
        logger.info("Controller merging stopped")

    # Modify the combine_inputs method to send state to virtual controller
    def combine_inputs(self):
        # Combine inputs from both controllers using the specified logic
        # Clear previous combined state
        self.combined_state.clear()
        self.combined_axes.clear()
        
        # Combine button inputs with "first input priority" logic
        # For digital inputs (buttons), use OR logic
        for input_name, state in self.player1_inputs.items():
            if state:
                self.combined_state[input_name] = True
        
        for input_name, state in self.player2_inputs.items():
            # Only add player 2's input if player 1 isn't already using it
            if state and not self.combined_state.get(input_name, False):
                self.combined_state[input_name] = True
        
        # Combine analog inputs with "first input gets priority" logic
        # For analog inputs, only use player 2's input if player 1 isn't using it
        for axis_name, value in self.player1_axes.items():
            # Only consider non-zero values as active inputs
            if abs(value) > 0.1:  # Small deadzone
                self.combined_axes[axis_name] = value
        
        for axis_name, value in self.player2_axes.items():
            # Only use player 2's input if player 1 isn't using it
            if abs(value) > 0.1 and abs(self.combined_axes.get(axis_name, 0)) <= 0.1:
                self.combined_axes[axis_name] = value
        
        # Update the virtual controller with the combined state
        if self.is_running:
            self.virtual_controller.update_state(self.combined_state, self.combined_axes)

    def merger_loop(self):
        """Main loop for merging controller inputs"""
        try:
            # Here we would implement the actual virtual controller creation and input combination
            # For this demo, we'll just process the inputs and log them
            
            logger.info("Starting controller merger loop")
            
            while self.is_running:
                # Process pygame events to get controller updates
                pygame.event.pump()
                
                # Update player states
                self.update_controller_states()
                
                # Combine inputs based on "first input gets priority" logic
                self.combine_inputs()
                
                # Here we would send the combined state to the virtual controller
                # For now, we'll just log it
                logger.debug(f"Combined state: {dict(self.combined_state)}")
                
                # Limit loop rate
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error in merger loop: {e}")
            self.stop_merging()

    def update_controller_states(self):
        """Update the state dictionaries for each controller"""
        # Reset states
        self.player1_inputs.clear()
        self.player1_axes.clear()
        self.player2_inputs.clear()
        self.player2_axes.clear()
        
        # Process player 1 controller
        if self.player1_id is not None:
            try:
                joystick = pygame.joystick.Joystick(self.player1_id)
                
                # Get button states
                for i in range(joystick.get_numbuttons()):
                    self.player1_inputs[f"button_{i}"] = joystick.get_button(i)
                    
                # Get axis states
                for i in range(joystick.get_numaxes()):
                    self.player1_axes[f"axis_{i}"] = joystick.get_axis(i)
                    
                # Get hat states
                for i in range(joystick.get_numhats()):
                    hat = joystick.get_hat(i)
                    self.player1_inputs[f"hat_{i}_up"] = hat[1] > 0
                    self.player1_inputs[f"hat_{i}_down"] = hat[1] < 0
                    self.player1_inputs[f"hat_{i}_left"] = hat[0] < 0
                    self.player1_inputs[f"hat_{i}_right"] = hat[0] > 0
                    
            except pygame.error:
                logger.warning(f"Could not read from player 1 controller (ID: {self.player1_id})")
        
        # Process player 2 controller
        if self.player2_id is not None:
            try:
                joystick = pygame.joystick.Joystick(self.player2_id)
                
                # Get button states
                for i in range(joystick.get_numbuttons()):
                    self.player2_inputs[f"button_{i}"] = joystick.get_button(i)
                    
                # Get axis states
                for i in range(joystick.get_numaxes()):
                    self.player2_axes[f"axis_{i}"] = joystick.get_axis(i)
                    
                # Get hat states
                for i in range(joystick.get_numhats()):
                    hat = joystick.get_hat(i)
                    self.player2_inputs[f"hat_{i}_up"] = hat[1] > 0
                    self.player2_inputs[f"hat_{i}_down"] = hat[1] < 0
                    self.player2_inputs[f"hat_{i}_left"] = hat[0] < 0
                    self.player2_inputs[f"hat_{i}_right"] = hat[0] > 0
                    
            except pygame.error:
                logger.warning(f"Could not read from player 2 controller (ID: {self.player2_id})")


    def draw_controller(self, canvas, button_states, axis_states):
        """Draw a controller visualization on the given canvas"""
        canvas.delete("all")
        
        # Canvas dimensions
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        # Calculate positions based on canvas size
        center_x = width / 2
        center_y = height / 2
        
        # Draw controller body
        canvas.create_rectangle(center_x - 80, center_y - 40, center_x + 80, center_y + 40, fill="lightgray", outline="black")
        
        # Left analog stick
        left_stick_x = center_x - 50
        left_stick_y = center_y - 10
        left_stick_offset_x = axis_states.get("axis_0", 0) * 10
        left_stick_offset_y = axis_states.get("axis_1", 0) * 10
        canvas.create_oval(left_stick_x - 15, left_stick_y - 15, left_stick_x + 15, left_stick_y + 15, fill="gray", outline="black")
        canvas.create_oval(left_stick_x - 5 + left_stick_offset_x, left_stick_y - 5 + left_stick_offset_y, 
                          left_stick_x + 5 + left_stick_offset_x, left_stick_y + 5 + left_stick_offset_y, 
                          fill="black")
        
        # Right analog stick
        right_stick_x = center_x + 50
        right_stick_y = center_y - 10
        right_stick_offset_x = axis_states.get("axis_2", 0) * 10
        right_stick_offset_y = axis_states.get("axis_3", 0) * 10
        canvas.create_oval(right_stick_x - 15, right_stick_y - 15, right_stick_x + 15, right_stick_y + 15, fill="gray", outline="black")
        canvas.create_oval(right_stick_x - 5 + right_stick_offset_x, right_stick_y - 5 + right_stick_offset_y, 
                          right_stick_x + 5 + right_stick_offset_x, right_stick_y + 5 + right_stick_offset_y, 
                          fill="black")
        
        # Buttons
        button_x = center_x + 40
        button_y = center_y + 10
        button_spacing = 15
        
        # Triangle
        canvas.create_polygon(button_x, button_y - button_spacing, 
                             button_x - 7, button_y - button_spacing + 7, 
                             button_x + 7, button_y - button_spacing + 7, 
                             fill="green" if button_states.get("button_3", False) else "lightgreen")
        
        # Circle
        canvas.create_oval(button_x + button_spacing - 7, button_y - 7, 
                          button_x + button_spacing + 7, button_y + 7, 
                          fill="red" if button_states.get("button_1", False) else "lightcoral")
        
        # Cross
        canvas.create_text(button_x, button_y + button_spacing, text="X", 
                          fill="blue" if button_states.get("button_0", False) else "lightblue")
        
        # Square
        canvas.create_rectangle(button_x - button_spacing - 7, button_y - 7, 
                               button_x - button_spacing + 7, button_y + 7, 
                               fill="purple" if button_states.get("button_2", False) else "plum")
        
        # D-pad
        dpad_x = center_x - 40
        dpad_y = center_y + 10
        dpad_size = 10
        
        # Up
        canvas.create_polygon(dpad_x, dpad_y - dpad_size, 
                             dpad_x - dpad_size, dpad_y, 
                             dpad_x + dpad_size, dpad_y, 
                             fill="black" if button_states.get("hat_0_up", False) else "gray")
        
        # Right
        canvas.create_polygon(dpad_x + dpad_size, dpad_y, 
                             dpad_x, dpad_y - dpad_size, 
                             dpad_x, dpad_y + dpad_size, 
                             fill="black" if button_states.get("hat_0_right", False) else "gray")
        
        # Down
        canvas.create_polygon(dpad_x, dpad_y + dpad_size, 
                             dpad_x - dpad_size, dpad_y, 
                             dpad_x + dpad_size, dpad_y, 
                             fill="black" if button_states.get("hat_0_down", False) else "gray")
        
        # Left
        canvas.create_polygon(dpad_x - dpad_size, dpad_y, 
                             dpad_x, dpad_y - dpad_size, 
                             dpad_x, dpad_y + dpad_size, 
                             fill="black" if button_states.get("hat_0_left", False) else "gray")
        
        # L1/R1 buttons
        canvas.create_rectangle(center_x - 70, center_y - 50, center_x - 30, center_y - 40, 
                               fill="darkgray" if button_states.get("button_4", False) else "gray")
        canvas.create_text(center_x - 50, center_y - 45, text="L1", fill="white")
        
        canvas.create_rectangle(center_x + 30, center_y - 50, center_x + 70, center_y - 40, 
                               fill="darkgray" if button_states.get("button_5", False) else "gray")
        canvas.create_text(center_x + 50, center_y - 45, text="R1", fill="white")
        
        # L2/R2 triggers
        l2_value = axis_states.get("axis_4", 0)
        r2_value = axis_states.get("axis_5", 0)
        
        # L2 trigger
        canvas.create_rectangle(center_x - 70, center_y - 65, center_x - 30, center_y - 55, outline="black")
        canvas.create_rectangle(center_x - 70, center_y - 65, center_x - 70 + 40 * ((l2_value + 1) / 2), center_y - 55, 
                               fill="darkgray")
        canvas.create_text(center_x - 50, center_y - 60, text="L2", fill="white")
        
        # R2 trigger
        canvas.create_rectangle(center_x + 30, center_y - 65, center_x + 70, center_y - 55, outline="black")
        canvas.create_rectangle(center_x + 30, center_y - 65, center_x + 30 + 40 * ((r2_value + 1) / 2), center_y - 55, 
                               fill="darkgray")
        canvas.create_text(center_x + 50, center_y - 60, text="R2", fill="white")
        
        # Options and Share buttons
        canvas.create_oval(center_x - 10, center_y - 20, center_x, center_y - 10, 
                          fill="darkgray" if button_states.get("button_8", False) else "gray")
        canvas.create_text(center_x - 5, center_y - 15, text="S", fill="white")
        
        canvas.create_oval(center_x, center_y - 20, center_x + 10, center_y - 10, 
                          fill="darkgray" if button_states.get("button_9", False) else "gray")
        canvas.create_text(center_x + 5, center_y - 15, text="O", fill="white")
        
        # Status label
        status_text = "Active" if any(button_states.values()) or any(abs(v) > 0.1 for v in axis_states.values()) else "Idle"
        canvas.create_text(center_x, height - 10, text=status_text)

def main():
    # Create root window
    root = tk.Tk()
    root.title("DualSense Controller Merger")
    
    # Initialize the app
    app = ControllerMerger(root)
    
    # Start the main loop
    root.mainloop()
    
    # Clean up
    pygame.quit()

if __name__ == "__main__":
    main()