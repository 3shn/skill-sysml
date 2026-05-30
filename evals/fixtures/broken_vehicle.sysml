package VehicleModel {
    private import ISQ::*;

    part def Vehicle {
        attribute mass :> ISQ::weight;
        part engine : Engine;
    }

    part deff Engine {
        attribute power :> ISQ::power;
    }
}
