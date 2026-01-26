package kr.co.himedia.smartcar.service;

import com.smartcar.sdk.AuthClient;
import com.smartcar.sdk.data.Auth;
import com.smartcar.sdk.SmartcarException;
import com.smartcar.sdk.Smartcar;
import com.smartcar.sdk.Vehicle;
import com.smartcar.sdk.data.VehicleAttributes;
import com.smartcar.sdk.data.VehicleIds;
import org.springframework.stereotype.Service;

@Service
public class SmartcarService {

    private final AuthClient authClient;

    public SmartcarService(AuthClient authClient) {
        this.authClient = authClient;
    }

    public String getAuthUrl() {
        // Define the permissions your app needs
        String[] scope = { "read_vehicle_info", "read_odometer", "read_location", "control_security" };
        return authClient.authUrlBuilder(scope).build();
    }

    public Auth exchangeCodeForToken(String code) throws SmartcarException {
        return authClient.exchangeCode(code);
    }

    public VehicleIds getVehicles(String accessToken) throws SmartcarException {
        return Smartcar.getVehicles(accessToken);
    }

    public VehicleAttributes getVehicleAttributes(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        return vehicle.attributes();
    }
}
