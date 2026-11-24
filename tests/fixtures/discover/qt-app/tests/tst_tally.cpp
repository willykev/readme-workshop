#include <QCommandLineParser>
#include <QKeySequence>
#include <QtTest>

class TestTally : public QObject {
    Q_OBJECT
private slots:
    void parses() {
        QCommandLineParser parser;
        parser.addOption({"selftest", "Run the self test"});
        QKeySequence debug("Ctrl+Alt+X");
        QVERIFY(!debug.isEmpty());
    }
};
QTEST_MAIN(TestTally)
