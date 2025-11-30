```java
@Test
public void testCreateOrder() {    
    // Create mock User object    
    User user = mock(User.class);   
    Order order=new Invoke(user);    
    // Stubbing methods of the URL object    
    when(user.getName()).thenReturn("Alice");    
    when(user.getTier(any())).thenReturn("BASIC");    
    // Perform tests on the mocked object    
    order.getOrderID(user);    
    verify(user). getName();   // verify
 }
@Test
 void testCreateGiftOrder() {
    User sender = mock(User.class); 
    User receiver = mock(User.class); 
    BookingService bookingService = new BookingService();
    // --- mock stub information ---
    when(sender.getName()).thenReturn("Alice"); 
    when(receiver.getName()).thenReturn("Bob"); 
    when(sender.getMembership()).thenReturn("GOLD");                     
    when(receiver.getMembership()).thenReturn("SILVER"); 
    // --- Call SUT ---
    String orderId = bookingService
            .createGiftOrder(List.of(sender, receiver), "FL123");
    assertNotNull(orderId);
}

void testDeleteGiftOrderAndVerifyUsers() {
    User sender = mock(User.class);
    User receiver = mock(User.class);
    BookingService bookingService = new BookingService();
    // --- mock stub information ---
    when(sender.getName()).thenReturn("Alice");
    when(receiver.getName()).thenReturn("Bob");
    when(sender.getMembership()).thenReturn("GOLD"); 
    when(receiver.getMembership()).thenReturn("SILVER"); 
    // --- mock get gift order id ---
    String orderID = bookingService.findGiftOrderId(sender, receiver);
    // --- Cancel Gift Order ---
    boolean canceled = bookingService.cancelGiftOrder(orderID);
    assertTrue(canceled);
}
```
