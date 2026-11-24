import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: win
    visible: true
    title: "Tally"

    Shortcut { sequence: "Ctrl+N"; onActivated: backend.add() }
    Shortcut { sequence: StandardKey.Quit; onActivated: Qt.quit() }
    Shortcut {
        sequences: ["Ctrl+Z", "Ctrl+Shift+Z"]
        onActivated: backend.undo()
    }
    // Shortcut { sequence: "Ctrl+Shift+D"; onActivated: backend.dump() }

    function _privateHelper() { return 0 }

    Label { anchors.centerIn: parent; text: "0" }
}
