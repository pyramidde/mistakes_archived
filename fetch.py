import sys
import time
from databaseConnect import storeMistake 
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget


def button_action(identifier, checked):
    # Replace this print with whatever you want the button to do.
    print(f"{identifier} is now {checked}")


def make_toggle_button(identifier, action):
    button = QPushButton(f"{identifier}: False")
    button.setObjectName(identifier)
    button.setCheckable(True)

    def on_toggle(checked):
        button.setText(f"{identifier}: {checked}")
        action(identifier, checked)

    button.toggled.connect(on_toggle)
    return button


class MistakesArchive(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_window()
        self.create_buttons()

    def setup_window(self):
        self.setWindowTitle("Mistakes Archive")
        self.resize(300, 150)
        self.layout = QVBoxLayout(self)

    def create_buttons(self):
        # Pass the function itself, without parentheses, to run it on toggles.
        self.first_button = make_toggle_button("Button 1", button_action)
        self.second_button = make_toggle_button("Button 2", button_action)
        self.third_button = make_toggle_button("Button 3", button_action)

        self.layout.addWidget(self.first_button)
        self.layout.addWidget(self.second_button)
        self.layout.addWidget(self.third_button)


def main():
    app = QApplication(sys.argv)
    window = MistakesArchive()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
