#include <iostream>
#include "../include/constant_extractor.h"

int main() {
    std::vector<Constant> oldConstants =
        extractConstants("test_data/old.cpp");

    std::vector<Constant> newConstants =
        extractConstants("test_data/new.cpp");

    std::vector<Change> changes =
        compareConstants(oldConstants, newConstants);

    generateJSON(changes);

    return 0;
}
