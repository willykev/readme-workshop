#include <QCommandLineParser>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include "backend.h"

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QCommandLineParser parser;
    parser.addHelpOption();
    parser.addOption({"new-window", "Open another window even when one is open"});
    parser.addOption({{"r", "reset"}, "Start the count at zero"});
    // parser.addOption({"legacy-mode", "Read counts in the old format"});
    parser.process(app);

    const QByteArray home = qgetenv("TALLY_HOME");
    const QByteArray hidden = qgetenv("_TALLY_PRIVATE");
    Backend backend(home);
    QQmlApplicationEngine engine;
    engine.load(QUrl("qrc:/Main.qml"));
    return app.exec();
}
