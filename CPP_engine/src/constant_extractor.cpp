
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

struct Constant {
    string name;
    string type;
    string value;
    int lineNumber;
};


vector<Constant> extractConstants(string filename) {

    vector<Constant> constants;
    ifstream file(filename);

    if (!file.is_open()) {
        cerr << "Could not open: " << filename << endl;
        return constants;
    }

    string line;
    int lineNumber = 0;

    while (getline(file, line)) {
        lineNumber++;

        string keyword, type, identifier, assignment, value;

        stringstream ss(line);
        ss >> keyword >> type >> identifier >> assignment >> value;

        if (keyword == "const" && assignment == "=") {

            if (!value.empty() && value.back() == ';') {
                value.pop_back();
            }

            Constant c;
            c.name = identifier;
            c.type = type;
            c.value = value;
            c.lineNumber = lineNumber;

            constants.push_back(c);
        }
    }

    file.close();
    return constants;
}

void compareConstants(
    const vector<Constant>& oldConstants,
    const vector<Constant>& newConstants
) {

    cout << "\n========== CHANGE REPORT ==========\n";

    
    for (const Constant& oldC : oldConstants) {

        bool found = false;

        for (const Constant& newC : newConstants) {

            if (oldC.name == newC.name) {
                found = true;

                if (oldC.value != newC.value ||
                    oldC.type != newC.type) {

                    cout << "MODIFIED: " << oldC.name
                         << " | " << oldC.value
                         << " -> " << newC.value
                         << " | Old line: " << oldC.lineNumber
                         << " | New line: " << newC.lineNumber
                         << endl;
                }
                else {
                    cout << "UNCHANGED: " << oldC.name << endl;
                }

                break;
            }
        }

        if (!found) {
            cout << "REMOVED: " << oldC.name
                 << " | Previous value: " << oldC.value
                 << " | Old line: " << oldC.lineNumber
                 << endl;
        }
    }


    for (const Constant& newC : newConstants) {

        bool found = false;

        for (const Constant& oldC : oldConstants) {
            if (newC.name == oldC.name) {
                found = true;
                break;
            }
        }

        if (!found) {
            cout << "ADDED: " << newC.name
                 << " | New value: " << newC.value
                 << " | New line: " << newC.lineNumber
                 << endl;
        }
    }

    cout << "===================================\n";
}

int main() {

    vector<Constant> oldConstants =
        extractConstants("test_data/old.cpp");

    vector<Constant> newConstants =
        extractConstants("test_data/new.cpp");

    compareConstants(oldConstants, newConstants);

    return 0;
}
