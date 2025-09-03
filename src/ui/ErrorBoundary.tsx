import React from 'react';
import { View, Text, Button } from 'react-native';

export default class ErrorBoundary extends React.Component<{children: any}, {hasError:boolean; err?:any}> {
  constructor(props:any){ super(props); this.state={hasError:false}; }
  static getDerivedStateFromError(err:any){ return { hasError:true, err }; }
  render(){
    if (this.state.hasError) {
      return (
        <View style={{ flex:1, alignItems:'center', justifyContent:'center', padding:16 }}>
          <Text style={{ fontWeight:'700', fontSize:18, marginBottom:8 }}>Something went wrong</Text>
          <Text style={{ color:'#666', marginBottom:12 }}>{String(this.state.err)}</Text>
          <Button title="Reload" onPress={()=>{ this.setState({hasError:false, err:null}); }} />
        </View>
      );
    }
    return this.props.children;
  }
}
