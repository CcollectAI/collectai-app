import React from 'react';
import Onboarding from '../../screens/Onboarding';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import SettingsProvider from '../settings/SettingsContext';
import SettingsScreen from '../../screens/Settings';
import Items from '../../screens/Items';
import ItemDetail from '../../screens/ItemDetail';
import MarketplacesScreen from '../../screens/MarketplacesScreen';
import Portfolio from '../../screens/Portfolio';
import Watchlist from '../../screens/Watchlist';
import SignIn from '../../screens/SignIn';
import AuthProvider, { useAuth } from '../auth/AuthContext';
import { Button } from 'react-native';
import EditItem from '../../screens/EditItem';
import SavedFilters from '../../screens/SavedFilters';
import ImportCSV from '../../screens/ImportCSV';
import Alerts from '../../screens/Alerts';
import Archived from '../../screens/Archived';
import ErrorBoundary from '../ui/ErrorBoundary';
import ExportAll from '../../screens/ExportAll';
import * as Linking from 'expo-linking';
import ScanAdd from '../../screens/ScanAdd';

const Stack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

function TabsRoot() {
  return (
    <Tabs.Navigator>
      <Tabs.Screen name="Items" component={Items} />
      <Tabs.Screen name="Portfolio" component={Portfolio} />
      <Tabs.Screen name="Watchlist" component={Watchlist} />
    </Tabs.Navigator>
  );
}

function RootNav() {
  const { user, loading, signOut } = useAuth();
  if (loading) return null;
  return (
    <Stack.Navigator>
      {user ? (
        <>
          <Stack.Screen
            name="Home"
            component={TabsRoot}
            options={{ headerRight: () => <Button title="Logout" onPress={signOut} /> }}
          />
          <Stack.Screen name="ItemDetail" component={ItemDetail} options={{ title: 'Item Detail' }} />
          <Stack.Screen name="Marketplaces" component={MarketplacesScreen} options={{ title: 'Marketplaces' }} />
          <Stack.Screen name="EditItem" component={EditItem} options={{ title: 'Edit Item' }} />
          <Stack.Screen name="SignIn" component={SignIn} options={{ headerShown:false }} />
          <Stack.Screen name="SavedFilters" component={SavedFilters} options={{ title: 'Saved Filters' }} />
          <Stack.Screen name="ImportCSV" component={ImportCSV} options={{ title: 'Import CSV' }} />
          <Stack.Screen name="Alerts" component={Alerts} options={{ title: 'Price Alerts' }} />
          <Stack.Screen name="Archived" component={Archived} options={{ title: 'Archived' }} />    
          <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: 'Settings' }} />
          <Stack.Screen name="ExportAll" component={ExportAll} options={{ title: 'Export All' }} />
          <Stack.Screen name="Onboarding" component={Onboarding} options={{ title: 'Onboarding' }} />
          <Stack.Screen name="ScanAdd" component={ScanAdd} options={{ title: 'Scan to Add' }} />
        )}
    </Stack.Navigator>
  );
}
const linking = {
  prefixes: [Linking.createURL('/'), 'collectors://'],
  config: {
    screens: {
      Home: {
        screens: {
          Items: 'items',
          Portfolio: 'portfolio',
          Watchlist: 'watchlist',
        }
      },
      ItemDetail: 'item/:id',
      Marketplaces: 'marketplaces',
      Alerts: 'alerts',
      ExportAll: 'export',
      Archived: 'archived',
      Settings: 'settings',
    }
  }
};

export default function AppNavigator() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <NavigationContainer>
         <ErrorBoundary>
          <RootNav />
        </ErrorBoundary>
        </NavigationContainer>
      </SettingsProvider>
    </AuthProvider>
  <NavigationContainer linking={linking}>
    <RootNav />
  </NavigationContainer>
);
}
