#include <iostream>
#include <fstream>
#include <string>

using namespace std;

int main() {

    ifstream oldFile("test_data/old.cpp");

    if (!oldFile.is_open()) {
        cout << "Could not open old file!" << endl;
        return 1;
    }

    string line;

    while (getline(oldFile, line)) {
        cout << line << endl;
    }

    oldFile.close();

    return 0;
}